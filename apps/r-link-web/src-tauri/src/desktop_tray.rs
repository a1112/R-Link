//! Native tray owns window lifetime; hiding never destroys the webview or its SSH sockets.
use serde::{Deserialize, Serialize};
use std::{path::PathBuf, sync::Mutex};
use tauri::{menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem}, tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent}, AppHandle, Emitter, Manager, Wry};

#[derive(Clone, Serialize, Deserialize)]
pub struct Preferences {
    close_to_tray: bool,
    #[serde(skip_deserializing)]
    tray_available: bool,
}
impl Default for Preferences {
    fn default() -> Self { Self { close_to_tray: true, tray_available: false } }
}
struct DesktopState {
    preferences: Mutex<Preferences>,
    path: PathBuf,
    menu_toggle: CheckMenuItem<Wry>,
}
fn should_hide(preferences: &Preferences) -> bool {
    preferences.close_to_tray && preferences.tray_available
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
    let state = app.state::<DesktopState>();
    let preferences = state.preferences.lock().map_err(|e| e.to_string())?.clone();
    Ok(preferences)
}
#[tauri::command]
pub fn set_close_to_tray(app: AppHandle, enabled: bool) -> Result<Preferences, String> {
    let state = app.state::<DesktopState>();
    let mut preferences = state.preferences.lock().map_err(|e| e.to_string())?;
    let mut updated = preferences.clone();
    updated.close_to_tray = enabled;
    // Commit only when persistence succeeds; callers can surface disk errors.
    std::fs::write(&state.path, serde_json::to_vec(&serde_json::json!({"close_to_tray": updated.close_to_tray})).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    *preferences = updated.clone();
    state.menu_toggle.set_checked(enabled).map_err(|e| e.to_string())?;
    app.emit_to("main", "desktop-preferences", &updated).map_err(|e| e.to_string())?;
    Ok(updated)
}
pub fn setup(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let directory = app.path().app_config_dir()?;
    std::fs::create_dir_all(&directory)?;
    let path = directory.join("desktop.json");
    let mut preferences: Preferences = std::fs::read(&path).ok().and_then(|data| serde_json::from_slice(&data).ok()).unwrap_or_default();
    let show = MenuItem::with_id(app, "show", "显示主窗口", true, None::<&str>)?;
    let devices = MenuItem::with_id(app, "devices", "设备管理", true, None::<&str>)?;
    let ssh = MenuItem::with_id(app, "ssh", "SSH 终端", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "系统设置", true, None::<&str>)?;
    let hide = MenuItem::with_id(app, "hide", "隐藏到托盘", true, None::<&str>)?;
    let toggle = CheckMenuItem::with_id(app, "close-to-tray", "关闭窗口后驻留", true, preferences.close_to_tray, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "退出 R-Link", true, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(app)?;
    let menu = Menu::with_items(app, &[&show, &devices, &ssh, &settings, &hide, &toggle, &separator, &quit])?;
    let mut tray = TrayIconBuilder::with_id("r-link-main")
        .tooltip("R-Link · 设备与网络管理")
        .menu(&menu).show_menu_on_left_click(false)
        .on_tray_icon_event(|tray, event| {
            if matches!(event, TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. }) {
                show_main(tray.app_handle());
            }
        })
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => show_main(app),
            "devices" | "ssh" | "settings" => {
                show_main(app);
                let _ = app.emit_to("main", "desktop-action", event.id.as_ref());
            },
            "hide" => { if let Some(window) = app.get_webview_window("main") { let _ = window.hide(); } },
            "close-to-tray" => {
                if let Ok(current) = desktop_preferences(app.clone()) {
                    if let Err(error) = set_close_to_tray(app.clone(), !current.close_to_tray) {
                        let state = app.state::<DesktopState>();
                        let _ = state.menu_toggle.set_checked(current.close_to_tray);
                        eprintln!("Could not save desktop preferences: {error}");
                    }
                }
            },
            // The backend is independently managed. Exiting this webview closes only its sockets.
            "quit" => app.exit(0),
            _ => {},
        });
    if let Some(icon) = app.default_window_icon() { tray = tray.icon(icon.clone()); }
    match tray.build(app) {
        Ok(_) => preferences.tray_available = true,
        Err(error) => eprintln!("Tray unavailable; window close will exit: {error}"),
    }
    app.manage(DesktopState { preferences: Mutex::new(preferences), path, menu_toggle: toggle });
    if let Some(window) = app.get_webview_window("main") {
        let handle = app.handle().clone();
        window.on_window_event(move |event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if desktop_preferences(handle.clone()).map(|p| should_hide(&p)).unwrap_or(false) {
                    if let Some(window) = handle.get_webview_window("main") {
                        // If hiding fails, retain the normal exit path rather than trapping the user.
                        if window.hide().is_ok() { api.prevent_close(); }
                    }
                }
            }
        });
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
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
        let p: Preferences = serde_json::from_str(r#"{"close_to_tray":false,"tray_available":true}"#).unwrap();
        assert!(!p.tray_available);
        assert!(!p.close_to_tray);
    }
}
