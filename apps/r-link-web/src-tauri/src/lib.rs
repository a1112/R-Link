#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{LogicalSize, Size};
#[cfg(not(mobile))]
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default().plugin(project_window_chrome::init())
        .plugin(project_resource_monitor::init())
        .invoke_handler(tauri::generate_handler![project_resource_monitor::project_resource_snapshot])
        .setup(|app| {
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
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

mod project_resource_monitor;

mod project_window_chrome;
