//! Desktop composition only. The reusable adapter and its authority live in r-link-core.
use r_link_core::bridgeproxy::{BridgeProxyClient, CoreRequest, CoreResponse};
use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Mutex,
};

#[derive(Default)]
pub struct BridgeProxyState {
    connection: Mutex<Option<BridgeProxyClient>>,
    generation: AtomicU64,
}

impl BridgeProxyState {
    fn begin_connect(&self) -> Result<u64, String> {
        let mut connection = self.connection.lock().map_err(|_| "Core 连接状态不可用")?;
        let generation = self
            .generation
            .fetch_add(1, Ordering::SeqCst)
            .wrapping_add(1);
        *connection = None;
        Ok(generation)
    }

    // The comparison and installation hold the same lock as disconnect, so an
    // earlier async connect cannot restore a grant after account cancellation.
    fn commit_connect(
        &self,
        generation: u64,
        install: impl FnOnce(&mut Option<BridgeProxyClient>),
    ) -> Result<(), String> {
        let mut connection = self.connection.lock().map_err(|_| "Core 连接状态不可用")?;
        if self.generation.load(Ordering::SeqCst) != generation {
            return Err("Core 连接请求已取消或被更新".into());
        }
        install(&mut connection);
        Ok(())
    }

    fn disconnect(&self) -> Result<(), String> {
        let mut connection = self.connection.lock().map_err(|_| "Core 连接状态不可用")?;
        self.generation.fetch_add(1, Ordering::SeqCst);
        *connection = None;
        Ok(())
    }
}

#[tauri::command]
pub fn bridgeproxy_adapter_info(
    state: tauri::State<'_, BridgeProxyState>,
) -> Result<Value, String> {
    let client = state.connection.lock().map_err(|_| "Core 连接状态不可用")?;
    Ok(client
        .as_ref()
        .map(BridgeProxyClient::info)
        .unwrap_or_else(|| {
            json!({
                "configured":false,"control_configured":false,"supported":cfg!(windows),
                "target":"local","endpoint_scope":"desktop-loopback","api_version":"v1"
            })
        }))
}

#[tauri::command]
pub async fn bridgeproxy_connect(
    state: tauri::State<'_, BridgeProxyState>,
    data_dir: String,
    allow_control: bool,
) -> Result<Value, String> {
    let generation = state.begin_connect()?;
    if data_dir.len() > 4096 || data_dir.chars().any(char::is_control) {
        return Err("Core 数据目录无效".into());
    }
    let client = tauri::async_runtime::spawn_blocking(move || {
        BridgeProxyClient::connect(data_dir, allow_control)
    })
    .await
    .map_err(|_| "无法读取本机 Core 配置")??;
    let health = client
        .request(CoreRequest {
            method: "GET".into(),
            path: "/v1/health".into(),
            body: None,
            revision: None,
            idempotency_key: None,
        })
        .await?;
    if health.status != 200 {
        return Err(format!("Core API 尚未就绪（HTTP {}）", health.status));
    }
    let info = client.info();
    state.commit_connect(generation, |connection| *connection = Some(client))?;
    Ok(info)
}

#[tauri::command]
pub fn bridgeproxy_disconnect(state: tauri::State<'_, BridgeProxyState>) -> Result<(), String> {
    state.disconnect()
}

#[tauri::command]
pub async fn bridgeproxy_request(
    state: tauri::State<'_, BridgeProxyState>,
    request: CoreRequest,
) -> Result<CoreResponse, String> {
    let (client, generation) = {
        let connection = state.connection.lock().map_err(|_| "Core 连接状态不可用")?;
        (
            connection.clone().ok_or("请先连接本机 Core")?,
            state.generation.load(Ordering::SeqCst),
        )
    };
    let response = client.request(request).await?;
    if state.generation.load(Ordering::SeqCst) != generation {
        return Err("Core 连接已更新，请刷新当前状态".into());
    }
    Ok(response)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;

    #[test]
    fn disconnect_revokes_a_pending_async_connect_before_it_can_install_a_grant() {
        let state = Arc::new(BridgeProxyState::default());
        let attempt = state.begin_connect().unwrap();
        let worker = state.clone();
        let (ready_tx, ready_rx) = std::sync::mpsc::channel();
        let (resume_tx, resume_rx) = std::sync::mpsc::channel();
        let thread = std::thread::spawn(move || {
            ready_tx.send(()).unwrap();
            resume_rx.recv().unwrap();
            worker.commit_connect(attempt, |_| panic!("cancelled grant must not be installed"))
        });
        ready_rx.recv().unwrap();
        state.disconnect().unwrap();
        resume_tx.send(()).unwrap();
        assert!(thread.join().unwrap().is_err());
        assert!(state.connection.lock().unwrap().is_none());
    }

    #[test]
    fn only_the_latest_connect_attempt_can_commit() {
        let state = BridgeProxyState::default();
        let old = state.begin_connect().unwrap();
        let latest = state.begin_connect().unwrap();
        assert!(state
            .commit_connect(old, |_| panic!("stale attempt"))
            .is_err());
        let mut installed = false;
        state.commit_connect(latest, |_| installed = true).unwrap();
        assert!(installed);
    }
}
