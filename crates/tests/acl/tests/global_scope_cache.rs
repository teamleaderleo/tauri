use std::sync::{Arc, Mutex};

use tauri::{
  plugin::{Builder as PluginBuilder, TauriPlugin},
  test::{mock_builder, mock_context, noop_assets, MockRuntime},
  utils::acl::resolved::{Resolved, ResolvedScope},
};

type ScopeSnapshot = (Vec<String>, Vec<String>);
type ScopeSink = Arc<Mutex<Option<ScopeSnapshot>>>;

fn scope_plugin(name: &'static str, sink: ScopeSink) -> TauriPlugin<MockRuntime> {
  PluginBuilder::<MockRuntime>::new(name)
    .setup(move |_app, api| {
      let scope = api.scope::<String>()?;
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
      *sink.lock().unwrap() = Some((allow, deny));
      Ok(())
    })
    .build()
}

fn context_with_scopes() -> tauri::Context<MockRuntime> {
  let mut context = mock_context(noop_assets());
  let resolved = Resolved {
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
  context
}

fn run_setup(mut app: tauri::App<MockRuntime>) {
  #[allow(deprecated)]
  app.run_iteration(|_, _| {});
}

fn snapshot(sink: &ScopeSink) -> ScopeSnapshot {
  sink
    .lock()
    .unwrap()
    .clone()
    .expect("plugin setup should capture its global scope")
}

#[test]
fn global_scope_cache_keeps_plugin_keys_distinct() {
  let alpha = ScopeSink::default();
  let beta = ScopeSink::default();

  let app = mock_builder()
    .plugin(scope_plugin("alpha", alpha.clone()))
    .plugin(scope_plugin("beta", beta.clone()))
    .build(context_with_scopes())
    .unwrap();

  run_setup(app);

  assert_eq!(
    snapshot(&alpha),
    (vec!["alpha-allow".to_string()], vec!["alpha-deny".to_string()])
  );
  assert_eq!(
    snapshot(&beta),
    (vec!["beta-allow".to_string()], vec!["beta-deny".to_string()])
  );
}

#[test]
fn empty_global_scope_lookup_does_not_poison_configured_plugin() {
  let empty = ScopeSink::default();
  let beta = ScopeSink::default();

  let app = mock_builder()
    .plugin(scope_plugin("empty", empty.clone()))
    .plugin(scope_plugin("beta", beta.clone()))
    .build(context_with_scopes())
    .unwrap();

  run_setup(app);

  assert_eq!(snapshot(&empty), (vec![], vec![]));
  assert_eq!(
    snapshot(&beta),
    (vec!["beta-allow".to_string()], vec!["beta-deny".to_string()])
  );
}
