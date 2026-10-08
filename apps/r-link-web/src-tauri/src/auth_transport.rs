use serde::Serialize;
use serde_json::{json, Value};
use std::time::Duration;

const MAX_RESPONSE: usize = 32 * 1024;

#[derive(Serialize)]
pub struct DesktopAuthResponse {
    status: u16,
    value: Value,
}

fn validated_request_url(value: &str, operation: &str) -> Result<tauri::Url, String> {
    if value.len() > 2048 || value.chars().any(|c| c <= ' ' || c == '\\') {
        return Err("桌面登录地址无效".into());
    }
    if !matches!(operation, "start" | "exchange") {
        return Err("不支持的桌面登录操作".into());
    }
    let url = tauri::Url::parse(value).map_err(|_| "桌面登录地址无效")?;
    let loopback = matches!(
        url.host_str(),
        Some("localhost" | "127.0.0.1" | "[::1]" | "::1")
    );
    if !(url.scheme() == "https" || (url.scheme() == "http" && loopback))
        || url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
        || !url
            .path()
            .ends_with(&format!("/api/auth/desktop/{operation}"))
    {
        return Err("只能请求受支持的桌面登录地址".into());
    }
    Ok(url)
}

fn valid_flow_value(value: &str) -> bool {
    (20..=100).contains(&value.len())
        && value
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || c == b'-' || c == b'_')
}

#[tauri::command]
pub async fn desktop_auth_request(
    url: String,
    operation: String,
    flow_id: Option<String>,
    poll_secret: Option<String>,
) -> Result<DesktopAuthResponse, String> {
    let url = validated_request_url(&url, &operation)?;
    let body = match operation.as_str() {
        "start" if flow_id.is_none() && poll_secret.is_none() => json!({}),
        "exchange" => {
            let flow = flow_id
                .filter(|v| valid_flow_value(v))
                .ok_or("桌面登录流程无效")?;
            let secret = poll_secret
                .filter(|v| valid_flow_value(v))
                .ok_or("桌面登录流程无效")?;
            json!({"flow_id": flow, "poll_secret": secret})
        }
        _ => return Err("桌面登录参数无效".into()),
    };
    // No cookies, service keys, browser fetch headers, redirects or global proxy changes.
    // Native TLS validates the certificate with the platform trust store.
    let client = reqwest::Client::builder()
        .no_proxy()
        .redirect(reqwest::redirect::Policy::none())
        .connect_timeout(Duration::from_secs(5))
        .timeout(Duration::from_secs(15))
        .build()
        .map_err(|_| "无法初始化安全登录连接")?;
    let mut response = client
        .post(url)
        .header("Accept", "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|_| "桌面登录 HTTPS 请求失败，请检查网络和证书")?;
    let status = response.status().as_u16();
    if !matches!(status, 200 | 202) {
        return Err(format!("桌面登录请求失败（HTTP {status}）"));
    }
    let content_type = response
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .split(';')
        .next()
        .unwrap_or("")
        .trim();
    if !content_type.eq_ignore_ascii_case("application/json")
        || response
            .content_length()
            .is_some_and(|v| v > MAX_RESPONSE as u64)
    {
        return Err("桌面登录响应格式或大小无效".into());
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| "无法读取桌面登录响应")? {
        if bytes.len() + chunk.len() > MAX_RESPONSE {
            return Err("桌面登录响应过大".into());
        }
        bytes.extend_from_slice(&chunk);
    }
    let value = serde_json::from_slice(&bytes).map_err(|_| "桌面登录响应不是有效 JSON")?;
    Ok(DesktopAuthResponse { status, value })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{Read, Write},
        net::TcpListener,
        thread,
    };

    #[test]
    #[ignore = "Manual approved cloud transport probe; opens no authentication UI"]
    fn live_cloud_flow_transport_without_authentication_ui() {
        let response = tauri::async_runtime::block_on(desktop_auth_request(
            "https://175.178.16.90/r-link/api/auth/desktop/start".into(),
            "start".into(),
            None,
            None,
        ))
        .expect("Native cloud HTTPS flow start failed");
        assert_eq!(response.status, 200);
        let flow = response.value["flow_id"].as_str().expect("Missing flow ID");
        let secret = response.value["poll_secret"]
            .as_str()
            .expect("Missing poll secret");
        assert!(valid_flow_value(flow) && valid_flow_value(secret));
        let pending = tauri::async_runtime::block_on(desktop_auth_request(
            "https://175.178.16.90/r-link/api/auth/desktop/exchange".into(),
            "exchange".into(),
            Some(flow.into()),
            Some(secret.into()),
        ))
        .expect("Native cloud HTTPS flow poll failed");
        assert_eq!(pending.status, 202);
        assert_eq!(pending.value["pending"], true);
        assert!(pending.value.get("token").is_none());
        println!("NATIVE_CLOUD_PROBE: start=200 exchange=202 pending=true tls_verified=true auth_ui_opened=false secrets_output=false");
    }

    fn server(response: String) -> (String, thread::JoinHandle<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let handle = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .set_read_timeout(Some(Duration::from_secs(5)))
                .unwrap();
            let mut request = Vec::new();
            loop {
                let mut buffer = [0; 1024];
                let count = stream.read(&mut buffer).unwrap();
                assert!(count > 0);
                request.extend_from_slice(&buffer[..count]);
                if let Some(end) = request.windows(4).position(|v| v == b"\r\n\r\n") {
                    let header = String::from_utf8_lossy(&request[..end]).to_lowercase();
                    let length: usize = header
                        .lines()
                        .find_map(|line| {
                            line.strip_prefix("content-length: ")
                                .and_then(|v| v.parse().ok())
                        })
                        .unwrap_or(0);
                    if request.len() >= end + 4 + length {
                        break;
                    }
                }
            }
            stream.write_all(response.as_bytes()).unwrap();
            String::from_utf8(request).unwrap()
        });
        (format!("http://{address}/r-link/api/auth/desktop"), handle)
    }

    #[test]
    fn restricts_transport_to_safe_fixed_auth_routes() {
        assert!(validated_request_url(
            "https://175.178.16.90/r-link/api/auth/desktop/start",
            "start"
        )
        .is_ok());
        assert!(validated_request_url(
            "http://127.0.0.1:8210/api/auth/desktop/exchange",
            "exchange"
        )
        .is_ok());
        for value in [
            "http://example.com/api/auth/desktop/start",
            "https://user:password@example.com/api/auth/desktop/start",
            "https://example.com/api/auth/desktop/start?secret=example",
            "https://example.com/api/auth/desktop/start#secret",
            "https://example.com/api/auth/logout",
            "https://example.com/api/auth/desktop/exchange",
        ] {
            assert!(validated_request_url(value, "start").is_err());
        }
        assert!(
            validated_request_url("https://example.com/api/auth/desktop/start", "delete").is_err()
        );
        assert!(!valid_flow_value("short"));
        assert!(!valid_flow_value("abcdefghijklmnopqrst/secret"));
    }

    #[test]
    fn native_exchange_has_no_cross_site_headers_cookies_or_service_key() {
        let (base, handle) = server("HTTP/1.1 202 Accepted\r\nContent-Type: application/json\r\nContent-Length: 16\r\nConnection: close\r\n\r\n{\"pending\":true}".into());
        let result = tauri::async_runtime::block_on(desktop_auth_request(
            format!("{base}/exchange"),
            "exchange".into(),
            Some("abcdefghijklmnopqrstuv".into()),
            Some("synthetic-poll-secret-abcdefghijklmnop".into()),
        ))
        .unwrap();
        assert_eq!(result.status, 202);
        assert_eq!(result.value["pending"], true);
        let request = handle.join().unwrap();
        let headers = request.split("\r\n\r\n").next().unwrap().to_lowercase();
        for header in ["sec-fetch-site:", "origin:", "cookie:", "authorization:"] {
            assert!(!headers.contains(header));
        }
        let body: Value = serde_json::from_str(request.split("\r\n\r\n").nth(1).unwrap()).unwrap();
        assert_eq!(
            body["poll_secret"],
            "synthetic-poll-secret-abcdefghijklmnop"
        );
    }

    #[test]
    fn redirects_cannot_forward_flow_secrets() {
        let (base, handle) = server("HTTP/1.1 307 Temporary Redirect\r\nLocation: https://example.com/api/auth/desktop/exchange\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".into());
        let result = tauri::async_runtime::block_on(desktop_auth_request(
            format!("{base}/start"),
            "start".into(),
            None,
            None,
        ));
        assert!(result.is_err());
        handle.join().unwrap();
    }

    #[test]
    fn oversized_login_responses_are_rejected_before_parsing() {
        let (base, handle) = server("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 32769\r\nConnection: close\r\n\r\n".into());
        let result = tauri::async_runtime::block_on(desktop_auth_request(
            format!("{base}/start"),
            "start".into(),
            None,
            None,
        ));
        assert!(result.is_err());
        handle.join().unwrap();
    }
}
