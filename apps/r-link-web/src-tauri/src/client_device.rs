use std::io::Read;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::time::{Duration, Instant};

#[derive(Debug, Default, serde::Serialize, serde::Deserialize, PartialEq)]
pub struct ManagementStatus {
    url: Option<String>,
    #[serde(default)]
    connected: bool,
}

#[derive(Debug, Default, serde::Serialize, serde::Deserialize, PartialEq)]
pub struct SignalStatus {
    #[serde(default)]
    connected: bool,
}

#[derive(Debug, Default, serde::Serialize, serde::Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ClientNetbirdStatus {
    daemon_status: Option<String>,
    #[serde(default)]
    management: ManagementStatus,
    #[serde(default)]
    signal: SignalStatus,
    netbird_ip: Option<String>,
}

#[derive(serde::Serialize)]
pub struct ClientDeviceInfo {
    hostname: Option<String>,
    platform: &'static str,
    netbird: Option<ClientNetbirdStatus>,
}

fn device_info(netbird: Option<ClientNetbirdStatus>) -> ClientDeviceInfo {
    ClientDeviceInfo {
        hostname: monitor_sysinfo::System::host_name(),
        platform: match std::env::consts::OS {
            "windows" => "windows",
            "macos" => "macos",
            "linux" => "linux",
            _ => "other",
        },
        netbird,
    }
}

#[cfg(windows)]
fn trusted_agent_path() -> Option<PathBuf> {
    // HKLM is the OS installation location, never a user-controlled PATH or env override.
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
    let path = directory.join("NetBird").join("netbird.exe");
    path.is_file().then_some(path)
}

#[cfg(not(windows))]
fn trusted_agent_path() -> Option<PathBuf> {
    // Fixed installation locations; do not resolve an executable through PATH.
    [
        "/usr/bin/netbird",
        "/usr/local/bin/netbird",
        "/opt/homebrew/bin/netbird",
    ]
    .into_iter()
    .map(PathBuf::from)
    .find(|path| path.is_file())
}

fn public_status(output: &[u8]) -> Option<ClientNetbirdStatus> {
    // Deserialize only this projection. No config, keys, peers, or raw errors leave native code.
    let status: ClientNetbirdStatus = serde_json::from_slice(output).ok()?;
    let clean =
        |value: &str, limit: usize| value.len() <= limit && !value.chars().any(char::is_control);
    if status
        .daemon_status
        .as_ref()
        .is_some_and(|value| !clean(value, 64))
        || status
            .management
            .url
            .as_ref()
            .is_some_and(|value| !clean(value, 2048))
        || status
            .netbird_ip
            .as_ref()
            .is_some_and(|value| !clean(value, 128))
    {
        return None;
    }
    Some(status)
}

struct StatusProcess(std::process::Child);

impl Drop for StatusProcess {
    fn drop(&mut self) {
        // Also clean up our own child on an early return or worker panic.
        if self.0.try_wait().ok().flatten().is_none() {
            let _ = self.0.kill();
            let _ = self.0.try_wait();
        }
    }
}

fn sample_agent() -> Option<ClientNetbirdStatus> {
    let started = Instant::now();
    let deadline = started + Duration::from_secs(3);
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
        command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    let mut owned = StatusProcess(command.spawn().ok()?);
    let child = &mut owned.0;
    let stdout = child.stdout.take()?;
    let (sender, receiver) = mpsc::sync_channel(1);
    std::thread::Builder::new()
        .name("netbird-status-output".into())
        .spawn(move || {
            let mut output = Vec::new();
            // Bound memory even if a large peer inventory or a broken CLI writes forever.
            let result = stdout.take(256 * 1024 + 1).read_to_end(&mut output);
            let _ = sender.send(if result.is_ok() && output.len() <= 256 * 1024 {
                Some(output)
            } else {
                None
            });
        })
        .ok()?;
    // Reserve cleanup time inside the three-second command budget.
    let process_deadline = deadline - Duration::from_millis(200);
    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                if !status.success() {
                    return None;
                }
                let output = receiver
                    .recv_timeout(deadline.saturating_duration_since(Instant::now()))
                    .ok()??;
                return public_status(&output);
            }
            Ok(None) if Instant::now() < process_deadline => std::thread::sleep(
                Duration::from_millis(20)
                    .min(process_deadline.saturating_duration_since(Instant::now())),
            ),
            _ => {
                // Only this status child is terminated; the Agent daemon is never touched.
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
pub async fn desktop_device_info() -> ClientDeviceInfo {
    tauri::async_runtime::spawn_blocking(|| device_info(sample_agent()))
        .await
        .unwrap_or_else(|_| device_info(None))
}

#[cfg(test)]
mod tests {
    use super::public_status;

    #[test]
    fn projects_only_public_status_fields() {
        let raw = br#"{"daemonStatus":"Connected","management":{"url":"https://175.178.16.90:7443","connected":true,"error":"private diagnostic"},"signal":{"connected":true,"error":"private diagnostic"},"netbirdIp":"100.126.3.139/16","PrivateKey":"must never leave native code","peers":{"details":[]}}"#;
        let output = serde_json::to_value(public_status(raw).unwrap()).unwrap();
        assert_eq!(output["netbirdIp"], "100.126.3.139/16");
        assert_eq!(output["management"]["connected"], true);
        assert_eq!(output.as_object().unwrap().len(), 4);
        assert!(output.get("PrivateKey").is_none());
        assert!(output["management"].get("error").is_none());
        assert!(output["signal"].get("error").is_none());
    }

    #[test]
    fn rejects_invalid_json_and_control_characters() {
        assert!(public_status(b"not json").is_none());
        assert!(public_status(br#"{"daemonStatus":"Connected\u0000"}"#).is_none());
    }
}
