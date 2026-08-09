from pathlib import Path

path = Path("crates/tauri/src/ipc/authority.rs")
text = path.read_text()

marker = '''  #[cfg(debug_assertions)]
  #[test]
  fn resolve_access_message() {
'''

tests = '''  #[test]
  fn deny_for_unrelated_origin_does_not_apply() {
    let command = "my-command";
    let window = "main";
    let webview = "main";
    let allowed_commands = [(
      command.to_string(),
      vec![ResolvedCommand {
        windows: vec![Pattern::new(window).unwrap()],
        ..Default::default()
      }],
    )]
    .into_iter()
    .collect();
    let denied_commands = [(
      command.to_string(),
      vec![ResolvedCommand {
        windows: vec![Pattern::new(window).unwrap()],
        context: ExecutionContext::Remote {
          url: "https://denied.example/*".parse().unwrap(),
        },
        ..Default::default()
      }],
    )]
    .into_iter()
    .collect();

    let authority = RuntimeAuthority::new(
      Default::default(),
      Resolved {
        allowed_commands,
        denied_commands,
        ..Default::default()
      },
    );

    assert!(authority
      .resolve_access(command, window, webview, &Origin::Local)
      .is_some());
  }

  #[test]
  fn deny_for_unrelated_window_does_not_apply() {
    let command = "my-command";
    let window = "main";
    let webview = "main";
    let allowed_commands = [(
      command.to_string(),
      vec![ResolvedCommand {
        windows: vec![Pattern::new(window).unwrap()],
        ..Default::default()
      }],
    )]
    .into_iter()
    .collect();
    let denied_commands = [(
      command.to_string(),
      vec![ResolvedCommand {
        windows: vec![Pattern::new("admin").unwrap()],
        ..Default::default()
      }],
    )]
    .into_iter()
    .collect();

    let authority = RuntimeAuthority::new(
      Default::default(),
      Resolved {
        allowed_commands,
        denied_commands,
        ..Default::default()
      },
    );

    assert!(authority
      .resolve_access(command, window, webview, &Origin::Local)
      .is_some());
  }

  #[test]
  fn deny_for_unrelated_webview_does_not_apply() {
    let command = "my-command";
    let window = "shell";
    let webview = "main-webview";
    let allowed_commands = [(
      command.to_string(),
      vec![ResolvedCommand {
        webviews: vec![Pattern::new(webview).unwrap()],
        ..Default::default()
      }],
    )]
    .into_iter()
    .collect();
    let denied_commands = [(
      command.to_string(),
      vec![ResolvedCommand {
        webviews: vec![Pattern::new("admin-webview").unwrap()],
        ..Default::default()
      }],
    )]
    .into_iter()
    .collect();

    let authority = RuntimeAuthority::new(
      Default::default(),
      Resolved {
        allowed_commands,
        denied_commands,
        ..Default::default()
      },
    );

    assert!(authority
      .resolve_access(command, window, webview, &Origin::Local)
      .is_some());
  }

'''

count = text.count(marker)
if count != 1:
  raise SystemExit(f"authority test marker: expected exactly one match, found {count}")

path.write_text(text.replace(marker, tests + marker, 1))
