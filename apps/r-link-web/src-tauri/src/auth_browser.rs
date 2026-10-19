use tauri_plugin_opener::OpenerExt;

fn validated_login_url(value: &str) -> Result<tauri::Url, String> {
    if value.len() > 2048 {
        return Err("登录地址过长".into());
    }
    let url = tauri::Url::parse(value).map_err(|_| "登录地址无效")?;
    let loopback = matches!(
        url.host_str(),
        Some("localhost" | "127.0.0.1" | "[::1]" | "::1")
    );
    let pairs: Vec<_> = url.query_pairs().collect();
    if !(url.scheme() == "https" || (url.scheme() == "http" && loopback))
        || url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.fragment().is_some()
        || !url.path().ends_with("/api/auth/desktop/login")
        || pairs.len() != 1
        || pairs[0].0 != "flow_id"
        || !(20..=128).contains(&pairs[0].1.len())
        || !pairs[0]
            .1
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || c == b'-' || c == b'_')
    {
        return Err("只能打开受支持的服务登录地址".into());
    }
    Ok(url)
}

#[tauri::command]
pub fn open_auth_login(app: tauri::AppHandle, url: String) -> Result<(), String> {
    let url = validated_login_url(&url)?;
    app.opener()
        .open_url(url.as_str(), None::<&str>)
        .map_err(|_| "无法打开系统浏览器".into())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_fixed_login_route_without_session_secrets() {
        assert!(validated_login_url(
            "https://175.178.16.90/r-link/api/auth/desktop/login?flow_id=abcdefghijklmnopqrstuv"
        )
        .is_ok());
        assert!(validated_login_url(
            "http://127.0.0.1:8210/api/auth/desktop/login?flow_id=abcdefghijklmnopqrstuv"
        )
        .is_ok());
    }

    #[test]
    fn rejects_local_files_insecure_remote_urls_and_extra_parameters() {
        for url in [
            "file:///C:/Windows/system32/cmd.exe",
            "http://example.com/api/auth/desktop/login?flow_id=abcdefghijklmnopqrstuv",
            "https://user:password@example.com/api/auth/desktop/login?flow_id=abcdefghijklmnopqrstuv",
            "https://example.com/api/auth/desktop/login?flow_id=abcdefghijklmnopqrstuv&poll_secret=secret",
            "https://example.com/api/auth/desktop/login?flow_id=abcdefghijklmnopqrstuv#secret",
            "https://example.com/api/auth/logout?flow_id=abcdefghijklmnopqrstuv",
        ] {
            assert!(validated_login_url(url).is_err(), "{url}");
        }
    }
}
