//! Native tray owns window lifetime; hiding never destroys the webview or its SSH sockets.
use serde::{Deserialize, Serialize};
use std::{path::PathBuf, sync::Mutex};
use tauri::{
    menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager, Wry,
};
use tauri_plugin_autostart::ManagerExt;

#[derive(Clone, PartialEq, Serialize, Deserialize)]
pub struct Preferences {
    close_to_tray: bool,
    #[serde(skip_deserializing)]
    tray_available: bool,
    #[serde(skip_deserializing)]
    autostart_enabled: Option<bool>,
    #[serde(skip_deserializing)]
    autostart_error: Option<String>,
}
impl Default for Preferences {
    fn default() -> Self {
        Self {
            close_to_tray: true,
            tray_available: false,
            autostart_enabled: None,
            autostart_error: None,
        }
    }
}
struct DesktopState {
    preferences: Mutex<Preferences>,
    path: PathBuf,
    menu_toggle: CheckMenuItem<Wry>,
    menu_autostart: CheckMenuItem<Wry>,
}
fn should_hide(preferences: &Preferences) -> bool {
    preferences.close_to_tray && preferences.tray_available
}
trait Autostart {
    fn is_enabled(&self) -> Result<bool, String>;
    fn set_enabled(&self, enabled: bool) -> Result<(), String>;
}
struct NativeAutostart<'a>(&'a AppHandle);
#[cfg(windows)]
const WINDOWS_RUN_KEY: &str = r#"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"#;

impl Autostart for NativeAutostart<'_> {
    fn is_enabled(&self) -> Result<bool, String> {
        #[cfg(windows)]
        {
            use winreg::{
                enums::{HKEY_CURRENT_USER, KEY_READ},
                RegKey,
            };
            let registry = RegKey::predef(HKEY_CURRENT_USER);
            let command = registry
                .open_subkey_with_flags(WINDOWS_RUN_KEY, KEY_READ)
                .and_then(|key| key.get_value::<String, _>(&self.0.package_info().name));
            let command = match command {
                Ok(command) => command,
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(false),
                Err(error) => return Err(error.to_string()),
            };
            let executable = std::env::current_exe().map_err(|error| error.to_string())?;
            if !windows_startup_matches(&command, &executable.display().to_string()) {
                return Ok(false);
            }
        }
        // The official manager also respects Windows Task Manager startup overrides.
        self.0
            .autolaunch()
            .is_enabled()
            .map_err(|error| error.to_string())
    }
    fn set_enabled(&self, enabled: bool) -> Result<(), String> {
        let manager = self.0.autolaunch();
        if enabled {
            #[cfg(windows)]
            {
                use winreg::{
                    enums::{HKEY_CURRENT_USER, KEY_SET_VALUE},
                    RegKey,
                };
                // Only R-Link's current-user Run value is written directly. The official
                // 2.5 plugin omits executable quoting; correct it before reporting success.
                let registry = RegKey::predef(HKEY_CURRENT_USER);
                let (key, _) = registry
                    .create_subkey_with_flags(WINDOWS_RUN_KEY, KEY_SET_VALUE)
                    .map_err(|error| error.to_string())?;
                manager.enable().map_err(|error| error.to_string())?;
                let executable = std::env::current_exe().map_err(|error| error.to_string())?;
                key.set_value(
                    &self.0.package_info().name,
                    &windows_startup_command(&executable.display().to_string()),
                )
                .map_err(|error| error.to_string())?;
            }
            #[cfg(not(windows))]
            manager.enable().map_err(|error| error.to_string())?;
        } else {
            manager.disable().map_err(|error| error.to_string())?;
        }
        Ok(())
    }
}
fn refresh_autostart(preferences: &mut Preferences, system: &impl Autostart) {
    match system.is_enabled() {
        Ok(enabled) => {
            // A failed write remains visible while its actual OS state is unchanged.
            // A recovered read or an external change clears an obsolete error.
            if preferences.autostart_enabled != Some(enabled) {
                preferences.autostart_error = None;
            }
            preferences.autostart_enabled = Some(enabled);
        }
        Err(error) => {
            preferences.autostart_enabled = None;
            preferences.autostart_error = Some(format!("无法读取系统自启状态：{error}"));
        }
    }
}
fn change_autostart(
    preferences: &mut Preferences,
    system: &impl Autostart,
    enabled: bool,
) -> Result<(), String> {
    refresh_autostart(preferences, system);
    let current = preferences.autostart_enabled.ok_or_else(|| {
        preferences
            .autostart_error
            .clone()
            .unwrap_or_else(|| "无法确认系统自启状态".into())
    })?;
    let write_error = if enabled || current != enabled {
        system
            .set_enabled(enabled)
            .err()
            .map(|error| format!("无法修改系统自启状态：{error}"))
    } else {
        None
    };
    // Even a platform error can occur after a partial write; always read back reality.
    refresh_autostart(preferences, system);
    let error = write_error.or_else(|| {
        if preferences.autostart_enabled == Some(enabled) {
            None
        } else if preferences.autostart_enabled.is_none() {
            preferences.autostart_error.clone()
        } else {
            Some("系统自启配置未生效，请检查系统权限后重试".into())
        }
    });
    preferences.autostart_error = error.clone();
    match error {
        Some(error) => Err(error),
        None => Ok(()),
    }
}
fn should_hide_at_startup(args: &[String], preferences: &Preferences) -> bool {
    preferences.tray_available && args.iter().skip(1).any(|arg| arg == "--autostart")
}
#[cfg(any(windows, test))]
fn windows_startup_command(executable: &str) -> String {
    format!("\"{executable}\" --autostart")
}
#[cfg(any(windows, test))]
fn windows_startup_matches(command: &str, executable: &str) -> bool {
    command == windows_startup_command(executable)
        || (!executable.chars().any(char::is_whitespace)
            && command == format!("{executable} --autostart"))
}
fn publish_preferences(
    app: &AppHandle,
    state: &DesktopState,
    preferences: &mut Preferences,
    emit: bool,
) {
    let menu_result = state
        .menu_autostart
        .set_checked(preferences.autostart_enabled.unwrap_or(false))
        .and_then(|_| {
            state
                .menu_autostart
                .set_enabled(preferences.autostart_enabled.is_some())
        });
    if let Err(error) = menu_result {
        eprintln!("Could not update autostart tray menu: {error}");
        if preferences.autostart_error.is_none() {
            preferences.autostart_error = Some(format!("无法更新托盘自启状态：{error}"));
        }
    }
    if emit {
        if let Err(error) = app.emit_to("main", "desktop-preferences", &*preferences) {
            eprintln!("Could not notify desktop preferences: {error}");
        }
    }
}
pub fn show_main(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}
#[tauri::command]
pub fn desktop_preferences(app: AppHandle) -> Result<Preferences, String> {
    let state = app
        .try_state::<DesktopState>()
        .ok_or("桌面设置尚未初始化")?;
    let mut preferences = state.preferences.lock().map_err(|e| e.to_string())?;
    let before = preferences.clone();
    refresh_autostart(&mut preferences, &NativeAutostart(&app));
    let changed = *preferences != before;
    publish_preferences(&app, &state, &mut preferences, changed);
    Ok(preferences.clone())
}
#[tauri::command]
pub fn set_autostart(app: AppHandle, enabled: bool) -> Result<Preferences, String> {
    let state = app.state::<DesktopState>();
    let mut preferences = state.preferences.lock().map_err(|e| e.to_string())?;
    let result = change_autostart(&mut preferences, &NativeAutostart(&app), enabled);
    publish_preferences(&app, &state, &mut preferences, true);
    result.map(|_| preferences.clone())
}
#[tauri::command]
pub fn hide_to_tray(app: AppHandle) -> Result<(), String> {
    if !desktop_preferences(app.clone())?.tray_available {
        return Err("系统托盘不可用，无法隐藏窗口".into());
    }
    app.get_webview_window("main")
        .ok_or("主窗口不可用")?
        .hide()
        .map_err(|e| e.to_string())
}
#[tauri::command]
pub fn set_close_to_tray(app: AppHandle, enabled: bool) -> Result<Preferences, String> {
    let state = app.state::<DesktopState>();
    let mut preferences = state.preferences.lock().map_err(|e| e.to_string())?;
    let mut updated = preferences.clone();
    updated.close_to_tray = enabled;
    // Commit only when persistence succeeds; callers can surface disk errors.
    std::fs::write(
        &state.path,
        serde_json::to_vec(&serde_json::json!({"close_to_tray": updated.close_to_tray}))
            .map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    *preferences = updated.clone();
    state
        .menu_toggle
        .set_checked(enabled)
        .map_err(|e| e.to_string())?;
    app.emit_to("main", "desktop-preferences", &updated)
        .map_err(|e| e.to_string())?;
    Ok(updated)
}
pub fn setup(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let directory = app.path().app_config_dir()?;
    std::fs::create_dir_all(&directory)?;
    let path = directory.join("desktop.json");
    let mut preferences: Preferences = std::fs::read(&path)
        .ok()
        .and_then(|data| serde_json::from_slice(&data).ok())
        .unwrap_or_default();
    // Startup state belongs to the OS; merely launching never enables or disables it.
    refresh_autostart(&mut preferences, &NativeAutostart(app.handle()));
    let show = MenuItem::with_id(app, "show", "显示主窗口", true, None::<&str>)?;
    let dashboard = MenuItem::with_id(app, "dashboard", "仪表盘", true, None::<&str>)?;
    let network = MenuItem::with_id(app, "network", "设备连接视图", true, None::<&str>)?;
    let plugins = MenuItem::with_id(app, "plugins", "插件管理", true, None::<&str>)?;
    let storage = MenuItem::with_id(app, "storage", "共享文件", true, None::<&str>)?;
    let devices = MenuItem::with_id(app, "devices", "设备管理", true, None::<&str>)?;
    let ssh = MenuItem::with_id(app, "ssh", "SSH 终端", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "系统设置", true, None::<&str>)?;
    let hide = MenuItem::with_id(app, "hide", "隐藏到托盘", true, None::<&str>)?;
    let toggle = CheckMenuItem::with_id(
        app,
        "close-to-tray",
        "关闭窗口后驻留",
        true,
        preferences.close_to_tray,
        None::<&str>,
    )?;
    let autostart = CheckMenuItem::with_id(
        app,
        "autostart",
        "登录系统后自动启动",
        preferences.autostart_enabled.is_some(),
        preferences.autostart_enabled.unwrap_or(false),
        None::<&str>,
    )?;
    let quit = MenuItem::with_id(app, "quit", "退出 R-Link", true, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(app)?;
    let menu = Menu::with_items(
        app,
        &[
            &show, &dashboard, &devices, &network, &ssh, &storage, &plugins, &settings, &hide,
            &toggle, &autostart, &separator, &quit,
        ],
    )?;
    let mut tray = TrayIconBuilder::with_id("r-link-main")
        .tooltip("R-Link · 设备与网络管理")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_tray_icon_event(|tray, event| {
            // Refresh an externally changed OS setting before the user acts on it.
            if matches!(
                event,
                TrayIconEvent::Enter { .. }
                    | TrayIconEvent::Click {
                        button: MouseButton::Right,
                        ..
                    }
            ) {
                let _ = desktop_preferences(tray.app_handle().clone());
            }
            if matches!(
                event,
                TrayIconEvent::Click {
                    button: MouseButton::Left,
                    button_state: MouseButtonState::Up,
                    ..
                }
            ) {
                show_main(tray.app_handle());
            }
        })
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => show_main(app),
            "dashboard" | "devices" | "network" | "ssh" | "storage" | "plugins" | "settings" => {
                show_main(app);
                let _ = app.emit_to("main", "desktop-action", event.id.as_ref());
            }
            "hide" => {
                let _ = hide_to_tray(app.clone());
            }
            "close-to-tray" => {
                if let Ok(current) = desktop_preferences(app.clone()) {
                    if let Err(error) = set_close_to_tray(app.clone(), !current.close_to_tray) {
                        let state = app.state::<DesktopState>();
                        let _ = state.menu_toggle.set_checked(current.close_to_tray);
                        eprintln!("Could not save desktop preferences: {error}");
                    }
                }
            }
            "autostart" => {
                let result = desktop_preferences(app.clone()).and_then(|current| {
                    let enabled = current.autostart_enabled.ok_or_else(|| {
                        current
                            .autostart_error
                            .unwrap_or_else(|| "无法确认系统自启状态".into())
                    })?;
                    set_autostart(app.clone(), !enabled)
                });
                if let Err(error) = result {
                    eprintln!("Could not change autostart: {error}");
                    show_main(app);
                    let _ = app.emit_to("main", "desktop-action", "settings");
                }
            }
            // The backend is independently managed. Exiting this webview closes only its sockets.
            "quit" => app.exit(0),
            _ => {}
        });
    if let Some(icon) = app.default_window_icon() {
        tray = tray.icon(icon.clone());
    }
    match tray.build(app) {
        Ok(_) => preferences.tray_available = true,
        Err(error) => eprintln!("Tray unavailable; window close will exit: {error}"),
    }
    let hide_on_startup =
        should_hide_at_startup(&std::env::args().collect::<Vec<_>>(), &preferences);
    app.manage(DesktopState {
        preferences: Mutex::new(preferences),
        path,
        menu_toggle: toggle,
        menu_autostart: autostart,
    });
    if let Some(window) = app.get_webview_window("main") {
        let handle = app.handle().clone();
        window.on_window_event(move |event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if desktop_preferences(handle.clone())
                    .map(|p| should_hide(&p))
                    .unwrap_or(false)
                {
                    if let Some(window) = handle.get_webview_window("main") {
                        // If hiding fails, retain the normal exit path rather than trapping the user.
                        if window.hide().is_ok() {
                            api.prevent_close();
                        }
                    }
                }
            }
        });
        if hide_on_startup {
            if let Err(error) = window.hide() {
                eprintln!("Could not hide autostart window: {error}");
                show_main(app.handle());
            }
        } else {
            show_main(app.handle());
        }
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::{Cell, RefCell};

    struct SystemAutostart {
        enabled: Cell<bool>,
        changes: Cell<usize>,
        read_error: RefCell<Option<String>>,
        write_error: Option<String>,
        ignore_change: bool,
    }
    impl SystemAutostart {
        fn new(enabled: bool) -> Self {
            Self {
                enabled: Cell::new(enabled),
                changes: Cell::new(0),
                read_error: RefCell::new(None),
                write_error: None,
                ignore_change: false,
            }
        }
    }
    impl Autostart for SystemAutostart {
        fn is_enabled(&self) -> Result<bool, String> {
            match self.read_error.borrow().clone() {
                Some(error) => Err(error),
                None => Ok(self.enabled.get()),
            }
        }
        fn set_enabled(&self, enabled: bool) -> Result<(), String> {
            self.changes.set(self.changes.get() + 1);
            if let Some(error) = &self.write_error {
                return Err(error.clone());
            }
            if !self.ignore_change {
                self.enabled.set(enabled);
            }
            Ok(())
        }
    }

    #[test]
    fn querying_system_autostart_reads_without_changing_it() {
        let system = SystemAutostart::new(true);
        let mut p = Preferences::default();
        refresh_autostart(&mut p, &system);
        assert_eq!(p.autostart_enabled, Some(true));
        assert_eq!(system.changes.get(), 0);
        system.enabled.set(false);
        refresh_autostart(&mut p, &system);
        assert_eq!(p.autostart_enabled, Some(false));
    }
    #[test]
    fn changing_autostart_reads_back_the_system_state_and_is_idempotent() {
        let system = SystemAutostart::new(false);
        let mut p = Preferences::default();
        change_autostart(&mut p, &system, false).unwrap();
        assert_eq!(system.changes.get(), 0);
        change_autostart(&mut p, &system, true).unwrap();
        assert_eq!(p.autostart_enabled, Some(true));
        assert_eq!(system.changes.get(), 1);
        change_autostart(&mut p, &system, false).unwrap();
        assert_eq!(p.autostart_enabled, Some(false));
    }
    #[test]
    fn enabling_autostart_refreshes_an_existing_registration_for_the_current_app() {
        let system = SystemAutostart::new(true);
        let mut p = Preferences::default();
        change_autostart(&mut p, &system, true).unwrap();
        assert_eq!(system.changes.get(), 1);
    }
    #[test]
    fn windows_registration_quotes_executable_paths_and_keeps_the_autostart_argument() {
        assert_eq!(
            windows_startup_command(r#"C:\Users\Test User\AppData\Local\R-Link\R-Link.exe"#),
            r#""C:\Users\Test User\AppData\Local\R-Link\R-Link.exe" --autostart"#
        );
        assert_eq!(
            windows_startup_command(r#"C:\Apps\R-Link.exe"#),
            r#""C:\Apps\R-Link.exe" --autostart"#
        );
    }
    #[test]
    fn windows_query_accepts_only_a_usable_registration_for_this_executable() {
        let spaced = r#"C:\Program Files\R-Link\R-Link.exe"#;
        assert!(windows_startup_matches(
            &format!("\"{spaced}\" --autostart"),
            spaced
        ));
        assert!(!windows_startup_matches(
            &format!("{spaced} --autostart"),
            spaced
        ));
        let plain = r#"C:\Apps\R-Link.exe"#;
        assert!(windows_startup_matches(
            &format!("{plain} --autostart"),
            plain
        ));
        assert!(!windows_startup_matches(
            r#""C:\Old\R-Link.exe" --autostart"#,
            plain
        ));
        assert!(!windows_startup_matches(
            &format!("\"{plain}\" --some-other-argument"),
            plain
        ));
    }
    #[test]
    fn failed_autostart_changes_preserve_actual_state_and_error_across_queries() {
        let mut system = SystemAutostart::new(false);
        system.write_error = Some("access denied".into());
        let mut p = Preferences::default();
        assert!(change_autostart(&mut p, &system, true)
            .unwrap_err()
            .contains("access denied"));
        assert_eq!(p.autostart_enabled, Some(false));
        refresh_autostart(&mut p, &system);
        assert!(p
            .autostart_error
            .as_ref()
            .unwrap()
            .contains("access denied"));
    }
    #[test]
    fn unreadable_autostart_is_unknown_and_never_mutated_until_query_recovers() {
        let system = SystemAutostart::new(true);
        *system.read_error.borrow_mut() = Some("read denied".into());
        let mut p = Preferences::default();
        assert!(change_autostart(&mut p, &system, false).is_err());
        assert_eq!(p.autostart_enabled, None);
        assert_eq!(system.changes.get(), 0);
        *system.read_error.borrow_mut() = None;
        refresh_autostart(&mut p, &system);
        assert_eq!(p.autostart_enabled, Some(true));
        assert_eq!(p.autostart_error, None);
    }
    #[test]
    fn successful_api_write_cannot_claim_startup_changed_without_readback() {
        let mut system = SystemAutostart::new(false);
        system.ignore_change = true;
        let mut p = Preferences::default();
        assert!(change_autostart(&mut p, &system, true).is_err());
        assert_eq!(p.autostart_enabled, Some(false));
        assert!(p.autostart_error.is_some());
    }
    #[test]
    fn startup_hides_only_autostart_launch_with_a_working_tray() {
        let ordinary = vec!["rlink.exe".to_owned()];
        let automatic = vec!["rlink.exe".to_owned(), "--autostart".to_owned()];
        let unrelated = vec!["rlink.exe".to_owned(), "--autostart=false".to_owned()];
        let mut p = Preferences::default();
        assert!(!should_hide_at_startup(&automatic, &p));
        p.tray_available = true;
        assert!(should_hide_at_startup(&automatic, &p));
        assert!(!should_hide_at_startup(&ordinary, &p));
        assert!(!should_hide_at_startup(&unrelated, &p));
        p.close_to_tray = false;
        assert!(should_hide_at_startup(&automatic, &p));
    }
    #[test]
    fn close_exits_without_a_working_tray_or_when_disabled() {
        let mut p = Preferences::default();
        assert!(!should_hide(&p));
        p.tray_available = true;
        assert!(should_hide(&p));
        p.close_to_tray = false;
        assert!(!should_hide(&p));
    }
    #[test]
    fn persisted_settings_cannot_claim_a_tray_exists() {
        let p: Preferences =
            serde_json::from_str(r#"{"close_to_tray":false,"tray_available":true}"#).unwrap();
        assert!(!p.tray_available);
        assert!(!p.close_to_tray);
    }
    #[test]
    fn persisted_settings_cannot_claim_os_autostart_is_enabled() {
        let p: Preferences = serde_json::from_str(
            r#"{"close_to_tray":true,"autostart_enabled":true,"autostart_error":"old error"}"#,
        )
        .unwrap();
        let value = serde_json::to_value(p).unwrap();
        assert!(value.as_object().unwrap().contains_key("autostart_enabled"));
        assert_eq!(value["autostart_enabled"], serde_json::Value::Null);
        assert_eq!(value["autostart_error"], serde_json::Value::Null);
    }
}
