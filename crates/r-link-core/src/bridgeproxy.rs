use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    fs::File,
    io::Read,
    path::{Path, PathBuf},
    time::Duration,
};

const CONTRACT: &str = include_str!("../../../contracts/bridgeproxy-v1.json");
const MAGIC: &[u8] = b"BRIDGEPROXY-CONTROL-DPAPI-1\0";
const MAX_RESPONSE: usize = 4 * 1024 * 1024;

#[derive(Clone, Deserialize, Serialize)]
pub struct RoutePolicy {
    pub method: String,
    pub path: String,
    pub scope: String,
    pub revision: bool,
}
#[derive(Deserialize)]
struct Contract {
    routes: Vec<RoutePolicy>,
}

pub fn routes() -> Vec<RoutePolicy> {
    serde_json::from_str::<Contract>(CONTRACT)
        .expect("compiled BridgeProxy contract")
        .routes
}

pub fn policy(method: &str, path: &str) -> Result<RoutePolicy, String> {
    if path.len() > 512
        || !path.starts_with("/v1/")
        || path
            .bytes()
            .any(|b| !b.is_ascii_alphanumeric() && !b"/._-".contains(&b))
        || path.split('/').any(|v| v == "." || v == "..")
    {
        return Err("不支持的 Core 请求路径".into());
    }
    routes()
        .into_iter()
        .find(|route| {
            if route.method != method {
                return false;
            }
            let template: Vec<_> = route.path.split('/').collect();
            let actual: Vec<_> = path.split('/').collect();
            template.len() == actual.len()
                && template.iter().zip(actual).all(|(expected, value)| {
                    if *expected == "{id}" {
                        !value.is_empty()
                            && value.len() <= 128
                            && value
                                .bytes()
                                .all(|b| b.is_ascii_alphanumeric() || b"_-".contains(&b))
                    } else {
                        *expected == value
                    }
                })
        })
        .ok_or_else(|| "Core 未提供此操作".into())
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct CoreRequest {
    pub method: String,
    pub path: String,
    pub body: Option<Value>,
    pub revision: Option<String>,
    pub idempotency_key: Option<String>,
}
#[derive(Serialize, Deserialize)]
pub struct CoreResponse {
    pub status: u16,
    pub body: Value,
    pub etag: Option<String>,
}

#[derive(Clone)]
pub struct BridgeProxyClient {
    data_dir: PathBuf,
    allow_control: bool,
}

// Deliberately not Debug/Serialize: the current Windows user's DPAPI credentials.
#[derive(Deserialize)]
struct Credentials {
    format: u8,
    read_token: String,
    control_token: String,
    port: u16,
    pid: u32,
    process_created: u64,
    active: bool,
}

impl BridgeProxyClient {
    pub fn connect(directory: impl AsRef<Path>, allow_control: bool) -> Result<Self, String> {
        #[cfg(not(windows))]
        return Err("本机 BridgeProxy Core 接入目前仅支持 Windows".into());
        #[cfg(windows)]
        {
            let path = directory.as_ref();
            if !path.is_absolute() {
                return Err("请选择 Core 的绝对数据目录".into());
            }
            let data_dir = path
                .canonicalize()
                .map_err(|_| "Core 数据目录不存在或不可读取")?;
            let client = Self {
                data_dir,
                allow_control,
            };
            client.credentials()?;
            Ok(client)
        }
    }

    pub fn info(&self) -> Value {
        json!({"configured":true,"control_configured":self.allow_control,"target":"local","endpoint_scope":"desktop-loopback","data_dir":self.data_dir.to_string_lossy(),"api_version":"v1"})
    }

    fn credentials(&self) -> Result<Credentials, String> {
        let path = self.data_dir.join("control-api.protected");
        reject_reparse(&self.data_dir)?;
        reject_reparse(&path)?;
        let mut bytes = Vec::new();
        File::open(path)
            .map_err(|_| "Core 凭据尚不可用，请先启动 Core API")?
            .take(65537)
            .read_to_end(&mut bytes)
            .map_err(|_| "无法读取 Core 凭据")?;
        if bytes.len() > 65536 || !bytes.starts_with(MAGIC) {
            return Err("Core 凭据格式无效".into());
        }
        let mut plain = unprotect(&bytes[MAGIC.len()..])?;
        let value = serde_json::from_slice::<Credentials>(&plain)
            .map_err(|_| "Core 凭据格式无效".to_string());
        plain.fill(0);
        let credentials = value?;
        if credentials.format != 1
            || credentials.port == 0
            || !valid_token(&credentials.read_token)
            || !valid_token(&credentials.control_token)
            || credentials.read_token == credentials.control_token
        {
            return Err("Core 凭据格式无效".into());
        }
        if !credentials.active || !process_matches(credentials.pid, credentials.process_created) {
            return Err("Core API 未运行，请先启动独立 Core 或 BridgeProxy".into());
        }
        Ok(credentials)
    }

    pub async fn request(&self, request: CoreRequest) -> Result<CoreResponse, String> {
        let route = validate(&request, self.allow_control)?;
        // Reload after every request boundary: rotations are observed without retrying writes.
        let credentials = self.credentials()?;
        send(request, route, credentials).await
    }
}

fn valid_token(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|b| b.is_ascii_hexdigit())
}

fn validate(request: &CoreRequest, allow_control: bool) -> Result<RoutePolicy, String> {
    let route = policy(&request.method, &request.path)?;
    if route.scope == "control" && !allow_control {
        return Err("尚未授权 R-Link 控制本机 Core，请重新连接并明确启用控制".into());
    }
    for value in [&request.revision, &request.idempotency_key]
        .into_iter()
        .flatten()
    {
        if value.is_empty()
            || value.len() > 256
            || !value.bytes().all(|b| (0x21..=0x7e).contains(&b))
        {
            return Err("Core 请求版本或幂等标识无效".into());
        }
    }
    if route.revision && request.revision.is_none() {
        return Err("请先刷新配置，再提交带版本的修改".into());
    }
    if request.method == "GET" && request.body.as_ref().is_some_and(|v| !v.is_null()) {
        return Err("读取请求不接受请求体".into());
    }
    if serde_json::to_vec(&request.body)
        .map_err(|_| "请求体无效")?
        .len()
        > 1024 * 1024
    {
        return Err("Core 请求体过大".into());
    }
    Ok(route)
}

async fn send(
    request: CoreRequest,
    route: RoutePolicy,
    credentials: Credentials,
) -> Result<CoreResponse, String> {
    let client = reqwest::Client::builder()
        .no_proxy()
        .redirect(reqwest::redirect::Policy::none())
        .connect_timeout(Duration::from_secs(3))
        .timeout(Duration::from_secs(12))
        .build()
        .map_err(|_| "无法初始化 Core 连接")?;
    let path = if request.path == "/v1/pairings/control" {
        "/v1/pairings"
    } else {
        &request.path
    };
    let token = if route.scope == "control" {
        &credentials.control_token
    } else {
        &credentials.read_token
    };
    let method =
        reqwest::Method::from_bytes(request.method.as_bytes()).map_err(|_| "请求方法无效")?;
    let mut builder = client
        .request(
            method,
            format!("http://127.0.0.1:{}{path}", credentials.port),
        )
        .bearer_auth(token)
        .header("Accept", "application/json");
    if let Some(revision) = &request.revision {
        builder = builder.header("If-Match", revision);
    }
    if let Some(key) = &request.idempotency_key {
        builder = builder.header("Idempotency-Key", key);
    }
    if request.method != "GET" {
        builder = builder.json(request.body.as_ref().unwrap_or(&Value::Null));
    }
    let mut response = builder
        .send()
        .await
        .map_err(|_| "无法连接本机 Core，请检查其运行状态")?;
    let status = response.status().as_u16();
    let etag = response
        .headers()
        .get("etag")
        .and_then(|v| v.to_str().ok())
        .map(|value| {
            let mut value = value.to_owned();
            for token in [&credentials.read_token, &credentials.control_token] {
                value = value.replace(token, "[REDACTED]");
            }
            value
        });
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
            .is_some_and(|n| n > MAX_RESPONSE as u64)
    {
        return Err("Core 响应格式或大小无效".into());
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| "读取 Core 响应失败")? {
        if bytes.len() + chunk.len() > MAX_RESPONSE {
            return Err("Core 响应过大".into());
        }
        bytes.extend_from_slice(&chunk);
    }
    let mut body: Value = serde_json::from_slice(&bytes).map_err(|_| "Core 响应不是有效 JSON")?;
    if body.get("api_version").and_then(Value::as_str) != Some("v1") {
        return Err("Core API 版本不兼容".into());
    }
    if request.path == "/v1/openapi.json" {
        redact_tokens(
            &mut body,
            &[&credentials.read_token, &credentials.control_token],
        );
    } else {
        sanitize(
            &mut body,
            route.scope == "control" && request.path == "/v1/pairings/control",
            &[&credentials.read_token, &credentials.control_token],
        );
    }
    Ok(CoreResponse { status, body, etag })
}

fn sanitize(value: &mut Value, sas: bool, secrets: &[&str]) {
    match value {
        Value::Object(object) => {
            object.retain(|key, _| {
                !matches!(
                    key.to_ascii_lowercase().as_str(),
                    "read_token"
                        | "control_token"
                        | "authorization"
                        | "custom_json"
                        | "password"
                        | "key_pem"
                        | "api_secret"
                        | "token"
                        | "identity"
                        | "private_key"
                        | "private_key_pem"
                        | "tls_private_key"
                ) && (sas || key != "verification_code")
            });
            for child in object.values_mut() {
                sanitize(child, sas, secrets);
            }
        }
        Value::Array(values) => values
            .iter_mut()
            .for_each(|child| sanitize(child, sas, secrets)),
        Value::String(text) => {
            for secret in secrets {
                if !secret.is_empty() {
                    *text = text.replace(secret, "[REDACTED]");
                }
            }
        }
        _ => {}
    }
}

fn redact_tokens(value: &mut Value, secrets: &[&str]) {
    match value {
        Value::Object(object) => object.values_mut().for_each(|v| redact_tokens(v, secrets)),
        Value::Array(values) => values.iter_mut().for_each(|v| redact_tokens(v, secrets)),
        Value::String(text) => {
            for secret in secrets {
                if !secret.is_empty() {
                    *text = text.replace(secret, "[REDACTED]");
                }
            }
        }
        _ => {}
    }
}

#[cfg(windows)]
fn reject_reparse(path: &Path) -> Result<(), String> {
    use std::os::windows::fs::MetadataExt;
    if path
        .symlink_metadata()
        .map_err(|_| "Core 数据路径不可读取")?
        .file_attributes()
        & 0x400
        != 0
    {
        return Err("Core 数据路径不能是重解析点".into());
    }
    Ok(())
}
#[cfg(not(windows))]
fn reject_reparse(_: &Path) -> Result<(), String> {
    Err("本机 Core 凭据仅支持 Windows".into())
}

#[cfg(windows)]
fn unprotect(bytes: &[u8]) -> Result<Vec<u8>, String> {
    use windows_sys::Win32::{
        Foundation::LocalFree,
        Security::Cryptography::{
            CryptUnprotectData, CRYPTPROTECT_UI_FORBIDDEN, CRYPT_INTEGER_BLOB,
        },
    };
    let input = CRYPT_INTEGER_BLOB {
        cbData: bytes.len() as u32,
        pbData: bytes.as_ptr() as *mut u8,
    };
    let mut output: CRYPT_INTEGER_BLOB = unsafe { std::mem::zeroed() };
    let ok = unsafe {
        CryptUnprotectData(
            &input,
            std::ptr::null_mut(),
            std::ptr::null(),
            std::ptr::null_mut(),
            std::ptr::null(),
            CRYPTPROTECT_UI_FORBIDDEN,
            &mut output,
        )
    };
    if ok == 0 {
        return Err("无法读取 Core 凭据，请使用创建该 Core 的 Windows 账户".into());
    }
    let plain =
        unsafe { std::slice::from_raw_parts(output.pbData, output.cbData as usize).to_vec() };
    unsafe {
        std::ptr::write_bytes(output.pbData, 0, output.cbData as usize);
        LocalFree(output.pbData as _);
    }
    Ok(plain)
}
#[cfg(not(windows))]
fn unprotect(_: &[u8]) -> Result<Vec<u8>, String> {
    Err("本机 Core 凭据仅支持 Windows".into())
}

#[cfg(windows)]
fn process_matches(pid: u32, expected: u64) -> bool {
    use windows_sys::Win32::{
        Foundation::{CloseHandle, FILETIME, WAIT_TIMEOUT},
        System::Threading::{
            GetProcessTimes, OpenProcess, WaitForSingleObject, PROCESS_QUERY_LIMITED_INFORMATION,
            PROCESS_SYNCHRONIZE,
        },
    };
    if pid == 0 || expected == 0 {
        return false;
    }
    unsafe {
        let handle = OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SYNCHRONIZE,
            0,
            pid,
        );
        if handle.is_null() {
            return false;
        }
        let [mut created_time, mut exit_time, mut kernel_time, mut user_time]: [FILETIME; 4] =
            std::mem::zeroed();
        let ok = GetProcessTimes(
            handle,
            &mut created_time,
            &mut exit_time,
            &mut kernel_time,
            &mut user_time,
        ) != 0;
        let running = WaitForSingleObject(handle, 0) == WAIT_TIMEOUT;
        let created =
            (u64::from(created_time.dwHighDateTime) << 32) | u64::from(created_time.dwLowDateTime);
        CloseHandle(handle);
        ok && running && created == expected
    }
}
#[cfg(not(windows))]
fn process_matches(_: u32, _: u64) -> bool {
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    fn stub(response: Vec<u8>) -> (Credentials, std::thread::JoinHandle<String>) {
        use std::io::{Read, Write};
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let thread = std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .set_read_timeout(Some(Duration::from_secs(5)))
                .unwrap();
            stream
                .set_write_timeout(Some(Duration::from_secs(5)))
                .unwrap();
            let mut request = Vec::new();
            let mut chunk = [0; 4096];
            loop {
                let count = stream.read(&mut chunk).unwrap();
                if count == 0 {
                    break;
                }
                request.extend_from_slice(&chunk[..count]);
                if let Some(index) = request.windows(4).position(|part| part == b"\r\n\r\n") {
                    let head = String::from_utf8_lossy(&request[..index]);
                    let length = head
                        .lines()
                        .find_map(|line| {
                            let (name, value) = line.split_once(':')?;
                            name.eq_ignore_ascii_case("content-length")
                                .then(|| value.trim().parse::<usize>().unwrap())
                        })
                        .unwrap_or(0);
                    if request.len() >= index + 4 + length {
                        break;
                    }
                }
                assert!(request.len() <= 1024 * 1024 + 16384);
            }
            let _ = stream.write_all(&response);
            String::from_utf8(request).unwrap()
        });
        (
            Credentials {
                format: 1,
                read_token: "a".repeat(64),
                control_token: "b".repeat(64),
                port,
                pid: 1,
                process_created: 1,
                active: true,
            },
            thread,
        )
    }

    fn reply(status: &str, body: Value, extra: &str) -> Vec<u8> {
        let body = serde_json::to_vec(&body).unwrap();
        let mut response = format!("HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n{extra}\r\n", body.len()).into_bytes();
        response.extend(body);
        response
    }

    fn get(path: &str) -> CoreRequest {
        CoreRequest {
            method: "GET".into(),
            path: path.into(),
            body: None,
            revision: None,
            idempotency_key: None,
        }
    }

    #[tokio::test(flavor = "current_thread")]
    async fn real_http_reads_use_only_read_credentials_and_no_browser_or_external_auth_headers() {
        let (credentials, thread) = stub(reply(
            "200 OK",
            json!({"api_version":"v1","data":{"running":false,"verification_code":"12345678"}}),
            "",
        ));
        let request = get("/v1/status");
        let response = send(
            request.clone(),
            validate(&request, true).unwrap(),
            credentials,
        )
        .await
        .unwrap();
        let captured = thread.join().unwrap().to_ascii_lowercase();
        assert!(captured.starts_with("get /v1/status http/1.1"));
        assert!(captured.contains(&format!("authorization: bearer {}", "a".repeat(64))));
        assert!(!captured.contains(&"b".repeat(64)));
        for header in [
            "\r\norigin:",
            "\r\ncookie:",
            "\r\nproxy-authorization:",
            "\r\nx-api-key:",
            "\r\nx-rlink",
        ] {
            assert!(!captured.contains(header), "{header}");
        }
        assert!(response.body["data"].get("verification_code").is_none());
    }

    #[tokio::test(flavor = "current_thread")]
    async fn sas_uses_the_control_credential_only_at_the_explicit_alias() {
        let (credentials, thread) = stub(reply(
            "200 OK",
            json!({"api_version":"v1","data":{"pending":[{"verification_code":"12345678"}]}}),
            "",
        ));
        let request = get("/v1/pairings/control");
        assert!(validate(&request, false).is_err());
        let response = send(
            request.clone(),
            validate(&request, true).unwrap(),
            credentials,
        )
        .await
        .unwrap();
        let captured = thread.join().unwrap().to_ascii_lowercase();
        assert!(captured.starts_with("get /v1/pairings http/1.1"));
        assert!(captured.contains(&format!("authorization: bearer {}", "b".repeat(64))));
        assert_eq!(
            response.body["data"]["pending"][0]["verification_code"],
            "12345678"
        );
    }

    #[tokio::test(flavor = "current_thread")]
    async fn redirects_do_not_forward_local_credentials_to_another_listener() {
        let trap = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        trap.set_nonblocking(true).unwrap();
        let extra = format!(
            "Location: http://127.0.0.1:{}/stolen\r\n",
            trap.local_addr().unwrap().port()
        );
        let (credentials, thread) = stub(reply(
            "307 Temporary Redirect",
            json!({"api_version":"v1","error":{"message":"redirect refused"}}),
            &extra,
        ));
        let request = get("/v1/status");
        let response = send(
            request.clone(),
            validate(&request, false).unwrap(),
            credentials,
        )
        .await
        .unwrap();
        thread.join().unwrap();
        assert_eq!(response.status, 307);
        assert_eq!(
            trap.accept().unwrap_err().kind(),
            std::io::ErrorKind::WouldBlock
        );
    }

    #[tokio::test(flavor = "current_thread")]
    async fn declared_and_streamed_response_limits_are_enforced() {
        let headers = format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n", MAX_RESPONSE + 1);
        let (credentials, thread) = stub(headers.into_bytes());
        let request = get("/v1/status");
        let error = send(
            request.clone(),
            validate(&request, false).unwrap(),
            credentials,
        )
        .await
        .err()
        .unwrap();
        thread.join().unwrap();
        assert!(error.contains("大小"));
        let mut chunked = format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n{:x}\r\n", MAX_RESPONSE + 1).into_bytes();
        chunked.extend(vec![b'x'; MAX_RESPONSE + 1]);
        chunked.extend_from_slice(b"\r\n0\r\n\r\n");
        let (credentials, thread) = stub(chunked);
        let error = send(
            request.clone(),
            validate(&request, false).unwrap(),
            credentials,
        )
        .await
        .err()
        .unwrap();
        thread.join().unwrap();
        assert!(error.contains("过大"));
    }

    #[tokio::test(flavor = "current_thread")]
    async fn upstream_errors_and_etags_cannot_echo_credentials() {
        let read = "a".repeat(64);
        let control = "b".repeat(64);
        let body = json!({"api_version":"v1","error":{"message":format!("upstream {read} {control}"),"details":{"Authorization":format!("Bearer {control}"),"api_secret":"private","token":"private","password":"private"}}});
        let (credentials, thread) = stub(reply(
            "500 Internal Server Error",
            body,
            &format!("ETag: {control}\r\n"),
        ));
        let request = get("/v1/status");
        let response = send(
            request.clone(),
            validate(&request, false).unwrap(),
            credentials,
        )
        .await
        .unwrap();
        thread.join().unwrap();
        assert_eq!(response.status, 500);
        let serialized = serde_json::to_string(&response).unwrap();
        assert!(!serialized.contains(&read));
        assert!(!serialized.contains(&control));
        assert!(!serialized.contains("private"));
    }

    #[tokio::test(flavor = "current_thread")]
    async fn openapi_preserves_write_only_schema_fields_while_redacting_token_values() {
        let body = json!({"api_version":"v1","data":{"openapi":"3.1.0","components":{"schemas":{"OutboundPatch":{"properties":{"password":{"type":"string","writeOnly":true},"custom_json":{"type":"string","writeOnly":true},"authorization":{"description":"schema name"}}}}},"description":"a".repeat(64)}});
        let (credentials, thread) = stub(reply("200 OK", body, ""));
        let request = get("/v1/openapi.json");
        let response = send(
            request.clone(),
            validate(&request, false).unwrap(),
            credentials,
        )
        .await
        .unwrap();
        thread.join().unwrap();
        let fields = &response.body["data"]["components"]["schemas"]["OutboundPatch"]["properties"];
        assert_eq!(fields["password"]["writeOnly"], true);
        assert_eq!(fields["custom_json"]["writeOnly"], true);
        assert_eq!(fields["authorization"]["description"], "schema name");
        assert_eq!(response.body["data"]["description"], "[REDACTED]");
    }

    #[cfg(windows)]
    #[tokio::test(flavor = "current_thread")]
    #[ignore = "Requires an explicitly supplied isolated Core data directory and process ID"]
    async fn isolated_live_core_dpapi_adapter_roundtrip() {
        let directory = PathBuf::from(
            std::env::var("R_LINK_TEST_CORE_DIR").expect("isolated data directory required"),
        );
        assert!(directory.is_absolute());
        assert!(directory
            .file_name()
            .unwrap()
            .to_string_lossy()
            .starts_with("native-adapter-"));
        assert_eq!(
            directory.parent().unwrap().file_name().unwrap(),
            ".test-data"
        );
        let expected_pid: u32 = std::env::var("R_LINK_TEST_CORE_PID")
            .expect("isolated child PID required")
            .parse()
            .unwrap();
        let client = BridgeProxyClient::connect(&directory, false).unwrap();
        let credentials = client.credentials().unwrap();
        assert_eq!(credentials.pid, expected_pid);
        let manifest = client.request(get("/v1/capabilities")).await.unwrap();
        assert_eq!(manifest.status, 200);
        assert_eq!(manifest.body["data"]["host"]["pid"], expected_pid);
        assert_eq!(manifest.body["data"]["host"]["kind"], "daemon");
        assert_eq!(manifest.body["data"]["core"]["id"], "bridgeproxy-core");
        let snapshot = client.request(get("/v1/snapshot")).await.unwrap();
        assert_eq!(snapshot.status, 200);
        assert_eq!(
            snapshot.body["data"]["resources"]["/v1/status"]["running"],
            false
        );
        assert_eq!(
            snapshot.body["data"]["resources"]["/v1/features"]["native_gui"],
            false
        );
        assert!(snapshot.body["data"]["age_ms"].as_u64().unwrap() < 5000);
        let schema = client.request(get("/v1/openapi.json")).await.unwrap();
        assert_eq!(
            schema.body["data"]["components"]["schemas"]["OutboundPatch"]["properties"]
                ["custom_json"]["writeOnly"],
            true
        );
        assert!(
            schema.body["data"]["components"]["schemas"]["RulesPut"]["properties"]
                .get("final_action")
                .is_some()
        );
        assert!(client.request(get("/v1/pairings/control")).await.is_err());
        assert!(client
            .request(CoreRequest {
                method: "POST".into(),
                path: "/v1/service/start".into(),
                body: None,
                revision: None,
                idempotency_key: None
            })
            .await
            .is_err());
        for response in [&manifest, &snapshot, &schema] {
            let encoded = serde_json::to_string(response).unwrap();
            assert!(!encoded.contains(&credentials.read_token));
            assert!(!encoded.contains(&credentials.control_token));
        }
        let runtime = client.request(get("/v1/runtime")).await.unwrap();
        assert_eq!(runtime.body["data"]["running"], false);
    }

    #[test]
    fn paths_and_methods_cannot_escape_the_capability_contract() {
        for path in [
            "http://evil/v1/status",
            "/v1/links/../tokens/rotate",
            "/v1/links/%2e%2e",
            "/v1/status?token=x",
            "/v1/links/a/b",
            "/v1/unknown",
        ] {
            assert!(policy("GET", path).is_err(), "{path}");
        }
        assert!(policy("POST", "/v1/status").is_err());
        assert!(policy("PATCH", "/v1/links/abc-123").is_ok());
        assert_eq!(
            policy("GET", "/v1/pairings/control").unwrap().scope,
            "control"
        );
    }

    #[test]
    fn a_local_read_grant_cannot_mutate_or_read_pairing_proofs() {
        for (method, path) in [
            ("POST", "/v1/service/start"),
            ("GET", "/v1/pairings/control"),
        ] {
            assert!(validate(
                &CoreRequest {
                    method: method.into(),
                    path: path.into(),
                    body: None,
                    revision: None,
                    idempotency_key: None
                },
                false
            )
            .is_err());
        }
        let mut request = CoreRequest {
            method: "PATCH".into(),
            path: "/v1/config".into(),
            body: Some(json!({"name":"safe"})),
            revision: None,
            idempotency_key: None,
        };
        assert!(validate(&request, true).is_err());
        request.revision = Some("revision\r\nAuthorization: changed".into());
        assert!(validate(&request, true).is_err());
        request.revision = Some("revision".into());
        assert!(validate(&request, true).is_ok());
    }

    #[test]
    fn nested_snapshots_and_operation_results_do_not_leak_proofs_or_credentials() {
        let mut value = json!({"data":{"resources":[{"verification_code":"12345678","control_token":"secret","message":"prefix secret suffix","custom_json":"private"}]}});
        sanitize(&mut value, false, &["secret"]);
        assert_eq!(
            value,
            json!({"data":{"resources":[{"message":"prefix [REDACTED] suffix"}]}})
        );
    }
}
