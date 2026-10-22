use std::io::Read;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::time::{Duration, Instant};

#[derive(Default, serde::Serialize, serde::Deserialize)]
pub struct ControlStatus {
    #[serde(default)]
    connected: bool,
    last_success_at: Option<u64>,
}

#[derive(Default, serde::Serialize, serde::Deserialize)]
pub struct TunStatus {
    #[serde(default)]
    ready: bool,
    name: Option<String>,
    ip: Option<String>,
}

#[derive(Default, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    Vpn,
    #[default]
    TransportTest,
}

#[derive(serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum PeerPath {
    Direct,
    Relay,
    Probing,
    Offline,
    None,
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct PeerStatus {
    peer_id: String,
    ip: Option<String>,
    path: PeerPath,
    rtt_ms: Option<f64>,
    last_handshake: Option<u64>,
    handshake_age_seconds: Option<u64>,
    #[serde(default)]
    rx_bytes: u64,
    #[serde(default)]
    tx_bytes: u64,
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct FabricStatus {
    schema_version: u8,
    provider: String,
    device_id: Option<String>,
    name: Option<String>,
    control_url: Option<String>,
    #[serde(default)]
    control: ControlStatus,
    #[serde(default)]
    tun: TunStatus,
    #[serde(default)]
    peers: Vec<PeerStatus>,
    #[serde(default)]
    updated_at: u64,
    #[serde(default)]
    mode: Mode,
    status_error: Option<String>,
}

#[cfg(windows)]
fn trusted_agent_path() -> Option<PathBuf> {
    use winreg::enums::{HKEY_LOCAL_MACHINE, KEY_READ, KEY_WOW64_64KEY};
    let directory: String = winreg::RegKey::predef(HKEY_LOCAL_MACHINE)
        .open_subkey_with_flags(
            "SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
            KEY_READ | KEY_WOW64_64KEY,
        )
        .ok()?
        .get_value("ProgramFilesDir")
        .ok()?;
    let directory = PathBuf::from(directory);
    if !directory.is_absolute() {
        return None;
    }
    let path = directory
        .join("R-Link")
        .join("Agent")
        .join("rlink-agent.exe");
    path.is_file().then_some(path)
}

#[cfg(not(windows))]
fn trusted_agent_path() -> Option<PathBuf> {
    let path = PathBuf::from("/usr/local/libexec/r-link/rlink-agent");
    path.is_file().then_some(path)
}

fn public_status(output: &[u8]) -> Option<FabricStatus> {
    let mut status: FabricStatus = serde_json::from_slice(output).ok()?;
    let text =
        |value: &str, limit: usize| value.len() <= limit && !value.chars().any(char::is_control);
    let optional = |value: &Option<String>, limit: usize| {
        value.as_ref().is_none_or(|value| text(value, limit))
    };
    if status.schema_version != 1
        || status.provider != "rlink-fabric"
        || !optional(&status.device_id, 80)
        || !optional(&status.name, 160)
        || !optional(&status.tun.name, 80)
        || !optional(&status.tun.ip, 128)
        || status.peers.len() > 1024
        || status.peers.iter().any(|peer| {
            !text(&peer.peer_id, 80)
                || !optional(&peer.ip, 128)
                || peer.rtt_ms.is_some_and(|rtt| !rtt.is_finite() || rtt < 0.0)
        })
    {
        return None;
    }
    if let Some(value) = &status.control_url {
        let url = tauri::Url::parse(value).ok()?;
        let loopback = matches!(
            url.host_str(),
            Some("localhost" | "127.0.0.1" | "[::1]" | "::1")
        );
        if !text(value, 2048)
            || !(url.scheme() == "https" || (url.scheme() == "http" && loopback))
            || url.host_str().is_none()
            || !url.username().is_empty()
            || url.password().is_some()
            || url.query().is_some()
            || url.fragment().is_some()
        {
            return None;
        }
    }
    if !matches!(
        status.status_error.as_deref(),
        None | Some("stale" | "not_running" | "stopped" | "invalid_status" | "startup_failed")
    ) {
        return None;
    }
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .ok()?
        .as_secs();
    if (now.saturating_sub(status.updated_at) > 45 || status.updated_at > now.saturating_add(5))
        && status.status_error.as_deref() != Some("startup_failed")
    {
        status.status_error = Some("stale".into());
    }
    // A failed or stale sample must never remain an online-looking public result.
    if status.status_error.is_some() {
        status.control.connected = false;
        status.tun.ready = false;
    }
    Some(status)
}

struct StatusProcess(std::process::Child);
impl Drop for StatusProcess {
    fn drop(&mut self) {
        if self.0.try_wait().ok().flatten().is_none() {
            let _ = self.0.kill();
            let _ = self.0.try_wait();
        }
    }
}

fn sample_agent() -> Option<FabricStatus> {
    let deadline = Instant::now() + Duration::from_secs(3);
    let path = trusted_agent_path()?;
    if Instant::now() >= deadline - Duration::from_millis(200) {
        return None;
    }
    let mut command = Command::new(path);
    command
        .args(["status", "--json"])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000);
    }
    let mut owned = StatusProcess(command.spawn().ok()?);
    let child = &mut owned.0;
    let stdout = child.stdout.take()?;
    let (sender, receiver) = mpsc::sync_channel(1);
    std::thread::Builder::new()
        .name("rlink-agent-status-output".into())
        .spawn(move || {
            let mut output = Vec::new();
            let result = stdout.take(256 * 1024 + 1).read_to_end(&mut output);
            let _ = sender.send(if result.is_ok() && output.len() <= 256 * 1024 {
                Some(output)
            } else {
                None
            });
        })
        .ok()?;
    let process_deadline = deadline - Duration::from_millis(200);
    loop {
        match child.try_wait() {
            Ok(Some(exit)) => {
                let output = receiver
                    .recv_timeout(deadline.saturating_duration_since(Instant::now()))
                    .ok()??;
                let status = public_status(&output)?;
                return (exit.success()
                    || (exit.code() == Some(1) && status.status_error.is_some()))
                .then_some(status);
            }
            Ok(None) if Instant::now() < process_deadline => std::thread::sleep(
                Duration::from_millis(20)
                    .min(process_deadline.saturating_duration_since(Instant::now())),
            ),
            _ => {
                let _ = child.kill();
                while Instant::now() < deadline {
                    if child.try_wait().ok().flatten().is_some() {
                        break;
                    }
                    std::thread::sleep(
                        Duration::from_millis(5)
                            .min(deadline.saturating_duration_since(Instant::now())),
                    );
                }
                return None;
            }
        }
    }
}

#[tauri::command]
pub async fn desktop_fabric_info() -> Option<FabricStatus> {
    tauri::async_runtime::spawn_blocking(sample_agent)
        .await
        .ok()
        .flatten()
}

#[cfg(test)]
mod tests {
    use super::public_status;
    fn fixture() -> serde_json::Value {
        serde_json::json!({"schema_version":1,"provider":"rlink-fabric","device_id":"id","name":"Mac Air","control_url":"https://175.178.16.90/r-link","control":{"connected":true,"last_success_at":1,"agent_bearer":"private"},"tun":{"ready":true,"name":"utun4","ip":"100.90.0.2/24"},"peers":[],"mode":"transport-test","updated_at":std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs(),"private_key":"private","enrollment_token":"private"})
    }
    #[test]
    fn only_returns_public_projection() {
        let value =
            serde_json::to_value(public_status(&serde_json::to_vec(&fixture()).unwrap()).unwrap())
                .unwrap();
        assert!(value.get("private_key").is_none());
        assert!(value.get("enrollment_token").is_none());
        assert!(value["control"].get("agent_bearer").is_none());
        assert_eq!(value["mode"], "transport-test");
        let mut failed = fixture();
        failed["status_error"] = serde_json::json!("startup_failed");
        let value =
            serde_json::to_value(public_status(&serde_json::to_vec(&failed).unwrap()).unwrap())
                .unwrap();
        assert_eq!(value["status_error"], "startup_failed");
        assert_eq!(value["control"]["connected"], false);
        assert_eq!(value["tun"]["ready"], false);
        failed["updated_at"] = serde_json::json!(1);
        let value =
            serde_json::to_value(public_status(&serde_json::to_vec(&failed).unwrap()).unwrap())
                .unwrap();
        assert_eq!(value["status_error"], "startup_failed");
        failed["status_error"] =
            serde_json::json!("unexpected diagnostic containing private values");
        assert!(public_status(&serde_json::to_vec(&failed).unwrap()).is_none());
    }
    #[test]
    fn stale_state_is_never_online() {
        let mut raw = fixture();
        raw["updated_at"] = serde_json::json!(1);
        let value =
            serde_json::to_value(public_status(&serde_json::to_vec(&raw).unwrap()).unwrap())
                .unwrap();
        assert_eq!(value["status_error"], "stale");
        assert_eq!(value["control"]["connected"], false);
        assert_eq!(value["tun"]["ready"], false);
    }
    #[test]
    fn rejects_wrong_provider_and_credentials_in_urls() {
        let mut raw = fixture();
        raw["provider"] = serde_json::json!("netbird");
        assert!(public_status(&serde_json::to_vec(&raw).unwrap()).is_none());
        raw = fixture();
        raw["control_url"] =
            serde_json::json!("https://user:password@server.test/r-link?token=private");
        assert!(public_status(&serde_json::to_vec(&raw).unwrap()).is_none());
    }
}
