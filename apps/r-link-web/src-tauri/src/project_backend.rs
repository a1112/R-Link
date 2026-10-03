//! Owned packaged server. No release dependency on Python or a source checkout.
use std::{
    fs::{self, OpenOptions},
    io::{Read, Write},
    net::{SocketAddr, TcpListener, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tauri::Manager;

#[derive(Default)]
pub struct BackendState(pub Mutex<Option<Backend>>);

pub struct Backend {
    child: Child,
    session: String,
    port: u16,
}

fn request(port: u16, method: &str, path: &str, session: &str) -> Option<String> {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream = TcpStream::connect_timeout(&address, Duration::from_millis(200)).ok()?;
    stream
        .set_read_timeout(Some(Duration::from_millis(700)))
        .ok()?;
    stream
        .set_write_timeout(Some(Duration::from_millis(700)))
        .ok()?;
    write!(stream, "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\nContent-Length: 0\r\nX-Rbox-Session: {session}\r\n\r\n").ok()?;
    let mut response = String::new();
    stream.take(16_384).read_to_string(&mut response).ok()?;
    Some(response)
}

fn matches_health(response: &str, id: &str, session: &str) -> bool {
    if !(response.starts_with("HTTP/1.1 200 ") || response.starts_with("HTTP/1.0 200 ")) {
        return false;
    }
    let Some((_, body)) = response.split_once("\r\n\r\n") else {
        return false;
    };
    let Ok(value) = serde_json::from_str::<serde_json::Value>(body) else {
        return false;
    };
    value["status"] == "healthy" && value["service"] == id && value["session"] == session
}

fn runtime_path(exe: &Path, id: &str) -> PathBuf {
    let name = format!("{id}-server{}", if cfg!(windows) { ".exe" } else { "" });
    exe.parent()
        .unwrap_or_else(|| Path::new("."))
        .join("runtime")
        .join(name)
}

impl Backend {
    pub fn start(
        id: &str,
        _folder: &str,
        env_prefix: &str,
        port: u16,
        data: &Path,
    ) -> Result<Self, String> {
        fs::create_dir_all(data.join("logs")).map_err(|e| e.to_string())?;
        let exe = std::env::current_exe().map_err(|e| e.to_string())?;
        let binary = runtime_path(&exe, id);
        let mut command;
        if binary.is_file() {
            command = Command::new(&binary);
            command.current_dir(binary.parent().unwrap());
        } else {
            #[cfg(debug_assertions)]
            {
                let source = exe
                    .ancestors()
                    .chain(Path::new(env!("CARGO_MANIFEST_DIR")).ancestors())
                    .map(|p| p.join(format!("{_folder}-Server/desktop_runtime.py")))
                    .find(|p| p.is_file())
                    .ok_or_else(|| format!("缺少随包后台：{}", binary.display()))?;
                let python = std::env::var(format!("{env_prefix}_PYTHON")).unwrap_or_else(|_| {
                    if cfg!(windows) {
                        "python".into()
                    } else {
                        "python3".into()
                    }
                });
                command = Command::new(python);
                command.arg(&source).current_dir(source.parent().unwrap());
            }
            #[cfg(not(debug_assertions))]
            return Err(format!(
                "缺少随包后台：{}。请重新安装完整的软件包。",
                binary.display()
            ));
        }
        // Never reuse a random process which happens to own the fixed service port.
        let port = if TcpStream::connect_timeout(
            &SocketAddr::from(([127, 0, 0, 1], port)),
            Duration::from_millis(150),
        )
        .is_ok()
        {
            let listener = TcpListener::bind(("127.0.0.1", 0)).map_err(|e| e.to_string())?;
            listener.local_addr().map_err(|e| e.to_string())?.port()
        } else {
            port
        };
        let session = format!(
            "{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        );
        let log = OpenOptions::new()
            .create(true)
            .append(true)
            .open(data.join("logs/desktop-launch.log"))
            .map_err(|e| e.to_string())?;
        command
            .env(format!("{env_prefix}_USER_ROOT"), data)
            .env("RBOX_DESKTOP_SESSION", &session)
            .env("RBOX_DESKTOP_PARENT", std::process::id().to_string())
            .env("RBOX_DESKTOP_PORT", port.to_string())
            .env_remove("R_FONT_ADMIN_KEY")
            .env_remove("R_LINK_API_TOKEN")
            .env("PYTHONUTF8", "1")
            .stdin(Stdio::null())
            .stderr(Stdio::from(log.try_clone().map_err(|e| e.to_string())?))
            .stdout(Stdio::from(log));
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let child = command.spawn().map_err(|e| format!("后台启动失败：{e}"))?;
        let mut backend = Self {
            child,
            session,
            port,
        };
        let start = Instant::now();
        while start.elapsed() < Duration::from_secs(45) {
            if let Some(status) = backend.child.try_wait().map_err(|e| e.to_string())? {
                return Err(format!(
                    "后台提前退出（{status}）。请查看 {}",
                    data.join("logs/desktop-launch.log").display()
                ));
            }
            if request(port, "GET", "/rbox/health", "")
                .is_some_and(|response| matches_health(&response, id, &backend.session))
            {
                return Ok(backend);
            }
            thread::sleep(Duration::from_millis(100));
        }
        Err(format!(
            "后台在 45 秒内未就绪。请查看 {}",
            data.join("logs/desktop-launch.log").display()
        ))
    }

    pub fn stop(&mut self) {
        if self.child.try_wait().ok().flatten().is_some() {
            return;
        }
        let _ = request(self.port, "POST", "/rbox/shutdown", &self.session);
        let start = Instant::now();
        while start.elapsed() < Duration::from_secs(6) {
            if self.child.try_wait().ok().flatten().is_some() {
                return;
            }
            thread::sleep(Duration::from_millis(100));
        }
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl Drop for Backend {
    fn drop(&mut self) {
        self.stop();
    }
}

pub fn start(
    app: &tauri::AppHandle,
    id: &str,
    folder: &str,
    env_prefix: &str,
    port: u16,
) -> Result<(), String> {
    let data = app
        .path()
        .local_data_dir()
        .map_err(|e| e.to_string())?
        .join(folder);
    let backend = Backend::start(id, folder, env_prefix, port, &data)?;
    *app.state::<BackendState>()
        .0
        .lock()
        .map_err(|e| e.to_string())? = Some(backend);
    Ok(())
}

pub fn stop(app: &tauri::AppHandle) {
    if let Ok(mut state) = app.state::<BackendState>().0.lock() {
        state.take();
    }
}

#[tauri::command]
pub fn desktop_backend_endpoint(state: tauri::State<'_, BackendState>) -> Result<String, String> {
    let state = state.0.lock().map_err(|e| e.to_string())?;
    let backend = state.as_ref().ok_or("桌面后台未就绪")?;
    Ok(format!("http://127.0.0.1:{}", backend.port))
}

pub fn startup_error(folder: &str, error: &str) {
    eprintln!("{folder} 启动失败：{error}");
    #[cfg(windows)]
    {
        #[link(name = "user32")]
        extern "system" {
            fn MessageBoxW(
                window: *mut std::ffi::c_void,
                text: *const u16,
                caption: *const u16,
                kind: u32,
            ) -> i32;
        }
        let text: Vec<u16> = error.encode_utf16().chain(std::iter::once(0)).collect();
        let caption: Vec<u16> = format!("{folder} 启动失败")
            .encode_utf16()
            .chain(std::iter::once(0))
            .collect();
        unsafe {
            MessageBoxW(std::ptr::null_mut(), text.as_ptr(), caption.as_ptr(), 0x10);
        }
    }
}

/// Exercise the same packaged lifecycle without a WebView for release smoke checks.
pub fn runtime_check_args(id: &str, folder: &str, prefix: &str, port: u16) -> bool {
    let args: Vec<_> = std::env::args_os().collect();
    if args.get(1).is_none_or(|a| a != "--rbox-runtime-check") {
        return false;
    }
    let Some(report) = args.get(2).map(PathBuf::from) else {
        std::process::exit(2);
    };
    let data = report
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .join("runtime-check-user-data");
    let result = Backend::start(id, folder, prefix, port, &data).and_then(|mut backend| {
        backend.stop();
        if backend.child.try_wait().map_err(|e| e.to_string())?.is_none() {
            return Err("后台未正常退出".into());
        }
        Ok(serde_json::json!({"productId":id,"result":"passed","backendStarted":true,"backendStopped":true}))
    });
    let (value, code) = match result {
        Ok(value) => (value, 0),
        Err(error) => (
            serde_json::json!({"productId":id,"result":"failed","error":error}),
            1,
        ),
    };
    if fs::write(&report, serde_json::to_vec_pretty(&value).unwrap()).is_err() {
        std::process::exit(2);
    }
    std::process::exit(code);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn health_requires_product_and_owned_instance() {
        let good = "HTTP/1.1 200 OK\r\n\r\n{\"status\":\"healthy\",\"service\":\"r-font\",\"session\":\"owned\"}";
        assert!(matches_health(good, "r-font", "owned"));
        assert!(!matches_health(good, "r-link", "owned"));
        assert!(!matches_health(good, "r-font", "other"));
        assert!(!matches_health(
            "HTTP/1.1 503 Busy\r\n\r\n{}",
            "r-font",
            "owned"
        ));
    }

    #[test]
    fn runtime_lookup_is_independent_of_current_directory() {
        let exe = Path::new("package").join("rfont.exe");
        assert_eq!(
            runtime_path(&exe, "r-font"),
            Path::new("package/runtime").join(if cfg!(windows) {
                "r-font-server.exe"
            } else {
                "r-font-server"
            })
        );
    }
}
