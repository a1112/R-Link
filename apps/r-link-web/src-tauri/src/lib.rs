#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(not(mobile))]
mod window_geometry;
#[cfg(not(mobile))]
mod window_placement;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default();
    #[cfg(desktop)]
    let builder = builder.plugin(tauri_plugin_single_instance::init(|app, _, _| {
        desktop_tray::show_main(app);
    }));
    #[cfg(desktop)]
    let builder = builder.plugin(tauri_plugin_autostart::init(
        tauri_plugin_autostart::MacosLauncher::LaunchAgent,
        Some(vec!["--autostart"]),
    ));
    #[cfg(desktop)]
    let builder = builder.invoke_handler(tauri::generate_handler![
        client_device::desktop_device_info,
        fabric_device::desktop_fabric_info,
        auth_browser::open_auth_login,
        auth_transport::desktop_auth_request,
        project_resource_monitor::project_resource_snapshot,
        desktop_tray::desktop_preferences,
        desktop_tray::set_close_to_tray,
        desktop_tray::set_autostart,
        desktop_tray::hide_to_tray,
    ]);
    #[cfg(mobile)]
    let builder = builder.invoke_handler(tauri::generate_handler![
        project_resource_monitor::project_resource_snapshot
    ]);
    builder
        .plugin(tauri_plugin_opener::init())
        .plugin(project_window_chrome::init())
        .plugin(project_resource_monitor::init())
        .setup(|app| {
            #[cfg(desktop)]
            desktop_tray::setup(app)?;
            #[cfg(not(mobile))]
            window_placement::install(app, "main", (1060.0, 700.0), (800.0, 540.0), true);
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

mod project_resource_monitor;

mod project_window_chrome;

#[cfg(desktop)]
mod desktop_tray;

#[cfg(desktop)]
mod client_device;

#[cfg(desktop)]
mod fabric_device;

#[cfg(desktop)]
mod auth_browser;

#[cfg(desktop)]
mod auth_transport;
