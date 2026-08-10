use glob::Pattern;
use tauri::{
  ipc::{CallbackFn, GlobalScope, InvokeBody},
  plugin::{Builder as PluginBuilder, TauriPlugin},
  test::{mock_builder, mock_context, noop_assets, MockRuntime, INVOKE_KEY},
  utils::acl::resolved::{Resolved, ResolvedCommand, ResolvedScope},
  webview::InvokeRequest,
  WebviewWindow, WebviewWindowBuilder,
};

#[tauri::command]
fn read_scope(scope: GlobalScope<String>) -> (Vec<String>, Vec<String>) {
  let allow = scope
    .allows()
    .iter()
    .map(|value| value.as_ref().clone())
    .collect();
  let deny = scope
    .denies()
    .iter()
    .map(|value| value.as_ref().clone())
    .collect();
  (allow, deny)
}

fn scope_plugin(name: &'static str) -> TauriPlugin<MockRuntime> {
  PluginBuilder::<MockRuntime>::new(name)
    .invoke_handler(tauri::generate_handler![read_scope])
    .build()
}

fn allowed_command() -> Vec<ResolvedCommand> {
  vec![ResolvedCommand {
    windows: vec![Pattern::new("*").unwrap()],
    ..Default::default()
  }]
}

fn build_app() -> tauri::App<MockRuntime> {
  let mut context = mock_context(noop_assets());
  let resolved = Resolved {
    allowed_commands: [
      ("plugin:alpha|read_scope".to_string(), allowed_command()),
      ("plugin:beta|read_scope".to_string(), allowed_command()),
      ("plugin:empty|read_scope".to_string(), allowed_command()),
    ]
    .into_iter()
    .collect(),
    global_scope: [
      (
        "alpha".to_string(),
        ResolvedScope {
          allow: vec!["alpha-allow".to_string().into()],
          deny: vec!["alpha-deny".to_string().into()],
        },
      ),
      (
        "beta".to_string(),
        ResolvedScope {
          allow: vec!["beta-allow".to_string().into()],
          deny: vec!["beta-deny".to_string().into()],
        },
      ),
    ]
    .into_iter()
    .collect(),
    ..Default::default()
  };

  *context.runtime_authority_mut() = tauri::runtime_authority!(Default::default(), resolved);

  mock_builder()
    .plugin(scope_plugin("alpha"))
    .plugin(scope_plugin("beta"))
    .plugin(scope_plugin("empty"))
    .build(context)
    .unwrap()
}

fn build_webview(app: &tauri::App<MockRuntime>) -> WebviewWindow<MockRuntime> {
  WebviewWindowBuilder::new(app, "main", Default::default())
    .build()
    .unwrap()
}

fn invoke_scope(
  webview: &WebviewWindow<MockRuntime>,
  plugin: &str,
) -> (Vec<String>, Vec<String>) {
  let response = tauri::test::get_ipc_response(
    webview,
    InvokeRequest {
      cmd: format!("plugin:{plugin}|read_scope"),
      callback: CallbackFn(0),
      error: CallbackFn(1),
      url: if cfg!(any(windows, target_os = "android")) {
        "http://tauri.localhost"
      } else {
        "tauri://localhost"
      }
      .parse()
      .unwrap(),
      body: InvokeBody::default(),
      headers: Default::default(),
      invoke_key: INVOKE_KEY.to_string(),
    },
  )
  .unwrap_or_else(|error| panic!("{plugin} invocation rejected: {error}"));

  response.deserialize().unwrap()
}

#[test]
fn global_scope_cache_keeps_plugin_keys_distinct() {
  let app = build_app();
  let webview = build_webview(&app);

  assert_eq!(
    invoke_scope(&webview, "alpha"),
    (vec!["alpha-allow".to_string()], vec!["alpha-deny".to_string()])
  );
  assert_eq!(
    invoke_scope(&webview, "beta"),
    (vec!["beta-allow".to_string()], vec!["beta-deny".to_string()])
  );
}

#[test]
fn empty_global_scope_lookup_does_not_poison_configured_plugin() {
  let app = build_app();
  let webview = build_webview(&app);

  assert_eq!(invoke_scope(&webview, "empty"), (vec![], vec![]));
  assert_eq!(
    invoke_scope(&webview, "beta"),
    (vec!["beta-allow".to_string()], vec!["beta-deny".to_string()])
  );
}
