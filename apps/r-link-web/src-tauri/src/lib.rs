#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(not(mobile))]
use tauri::Manager;
use tauri::{LogicalSize, Size};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    #[cfg(desktop)]
    project_backend::runtime_check_args("r-link", "R-Link", "R_LINK", 8210);
    let builder = tauri::Builder::default().manage(project_backend::BackendState::default());
    #[cfg(desktop)]
    let builder = builder.plugin(tauri_plugin_single_instance::init(|app, _, _| {
        desktop_tray::show_main(app);
    }));
    #[cfg(desktop)]
    let builder = builder.invoke_handler(tauri::generate_handler![
        project_resource_monitor::project_resource_snapshot,
        desktop_tray::desktop_preferences,
        desktop_tray::set_close_to_tray,
        desktop_tray::hide_to_tray,
        project_backend::desktop_backend_endpoint,
    ]);
    #[cfg(mobile)]
    let builder = builder.invoke_handler(tauri::generate_handler![
        project_resource_monitor::project_resource_snapshot
    ]);
    builder
        .plugin(project_window_chrome::init())
        .plugin(project_resource_monitor::init())
        .setup(|app| {
            #[cfg(desktop)]
            if let Err(error) =
                project_backend::start(app.handle(), "r-link", "R-Link", "R_LINK", 8210)
            {
                project_backend::startup_error("R-Link", &error);
                return Err(std::io::Error::other(error).into());
            }
            #[cfg(desktop)]
            desktop_tray::setup(app)?;
            #[cfg(not(mobile))]
            {
                if let Some(window) = app.get_webview_window("main") {
                    if let Ok(Some(monitor)) = window.primary_monitor() {
                        let size = monitor.size();
                        let width = (size.width as f64 / monitor.scale_factor() * 0.7).round();
                        let height = (size.height as f64 / monitor.scale_factor() * 0.7).round();
                        let _ = window.set_size(Size::Logical(LogicalSize { width, height }));
                        let _ = window.center();
                    }
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                project_backend::stop(app);
            }
        });
}

mod project_resource_monitor;

mod project_window_chrome;

#[cfg(desktop)]
mod desktop_tray;
mod project_backend;
