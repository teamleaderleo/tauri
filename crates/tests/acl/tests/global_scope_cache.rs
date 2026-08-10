use std::sync::{
  atomic::{AtomicUsize, Ordering},
  Arc, Mutex,
};

use tauri::{
  ipc::ScopeObject,
  plugin::{Builder as PluginBuilder, TauriPlugin},
  test::{mock_builder, mock_context, noop_assets, MockRuntime},
  utils::acl::{
    resolved::{Resolved, ResolvedScope},
    Value,
  },
  AppHandle, Runtime,
};

#[cfg(feature = "dynamic-acl")]
use tauri::{
  ipc::CapabilityBuilder,
  plugin::PluginApi,
  utils::acl::{manifest::Manifest, Permission},
  Manager,
};

type ScopeSnapshot = (Vec<String>, Vec<String>);
type ScopeSink = Arc<Mutex<Option<ScopeSnapshot>>>;

static DESERIALIZATIONS: AtomicUsize = AtomicUsize::new(0);

#[derive(Debug)]
struct CountingScope(String);

impl ScopeObject for CountingScope {
  type Error = serde_json::Error;

  fn deserialize<R: Runtime>(_app: &AppHandle<R>, raw: Value) -> Result<Self, Self::Error> {
    DESERIALIZATIONS.fetch_add(1, Ordering::SeqCst);
    serde_json::from_value(raw.into()).map(Self)
  }
}

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

fn repeated_scope_plugin(name: &'static str) -> TauriPlugin<MockRuntime> {
  PluginBuilder::<MockRuntime>::new(name)
    .setup(move |_app, api| {
      let first = api.scope::<CountingScope>()?;
      let second = api.scope::<CountingScope>()?;

      assert_eq!(first.allows()[0].0, "alpha-allow");
      assert_eq!(first.denies()[0].0, "alpha-deny");
      assert_eq!(second.allows()[0].0, "alpha-allow");
      assert_eq!(second.denies()[0].0, "alpha-deny");
      Ok(())
    })
    .build()
}

fn resolved_scopes() -> Resolved {
  Resolved {
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
  }
}

fn context_with_scopes() -> tauri::Context<MockRuntime> {
  let mut context = mock_context(noop_assets());
  *context.runtime_authority_mut() =
    tauri::runtime_authority!(Default::default(), resolved_scopes());
  context
}

#[cfg(feature = "dynamic-acl")]
fn context_with_dynamic_scope_manifest() -> tauri::Context<MockRuntime> {
  let mut context = mock_context(noop_assets());
  let manifest = Manifest {
    permissions: [(
      "scope".to_string(),
      Permission {
        identifier: "scope".to_string(),
        ..Default::default()
      },
    )]
    .into_iter()
    .collect(),
    ..Default::default()
  };
  let acl = [("beta".to_string(), manifest)].into_iter().collect();
  *context.runtime_authority_mut() = tauri::runtime_authority!(acl, resolved_scopes());
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
    (
      vec!["alpha-allow".to_string()],
      vec!["alpha-deny".to_string()]
    )
  );
  assert_eq!(
    snapshot(&beta),
    (
      vec!["beta-allow".to_string()],
      vec!["beta-deny".to_string()]
    )
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
    (
      vec!["beta-allow".to_string()],
      vec!["beta-deny".to_string()]
    )
  );
}

#[test]
fn repeated_same_plugin_lookup_reuses_deserialized_scope() {
  DESERIALIZATIONS.store(0, Ordering::SeqCst);

  let app = mock_builder()
    .plugin(repeated_scope_plugin("alpha"))
    .build(context_with_scopes())
    .unwrap();

  run_setup(app);

  assert_eq!(DESERIALIZATIONS.load(Ordering::SeqCst), 2);
}

#[cfg(feature = "dynamic-acl")]
#[test]
fn dynamic_acl_refreshes_only_changed_plugin_scope_cache() {
  DESERIALIZATIONS.store(0, Ordering::SeqCst);

  let alpha_api: Arc<Mutex<Option<PluginApi<MockRuntime, ()>>>> = Default::default();
  let alpha_api_for_setup = alpha_api.clone();
  let alpha = PluginBuilder::<MockRuntime>::new("alpha")
    .setup(move |_app, api| {
      let scope = api.scope::<CountingScope>()?;
      assert_eq!(scope.allows()[0].0, "alpha-allow");
      assert_eq!(scope.denies()[0].0, "alpha-deny");
      *alpha_api_for_setup.lock().unwrap() = Some(api.clone());
      Ok(())
    })
    .build();

  let beta = PluginBuilder::<MockRuntime>::new("beta")
    .setup(move |app, api| {
      let before = api.scope::<CountingScope>()?;
      assert_eq!(before.allows()[0].0, "beta-allow");
      assert_eq!(before.denies()[0].0, "beta-deny");

      app.add_capability(
        CapabilityBuilder::new("runtime-beta").permission_scoped(
          "beta:scope",
          vec!["beta-extra".to_string()],
          Vec::<String>::new(),
        ),
      )?;

      let after = api.scope::<CountingScope>()?;
      assert_eq!(after.allows()[0].0, "beta-allow");
      assert_eq!(after.allows()[1].0, "beta-extra");
      assert_eq!(after.denies()[0].0, "beta-deny");

      let alpha_api = alpha_api
        .lock()
        .unwrap()
        .as_ref()
        .expect("alpha plugin setup should run first")
        .clone();
      let alpha_after = alpha_api.scope::<CountingScope>()?;
      assert_eq!(alpha_after.allows()[0].0, "alpha-allow");
      assert_eq!(alpha_after.denies()[0].0, "alpha-deny");
      Ok(())
    })
    .build();

  let app = mock_builder()
    .plugin(alpha)
    .plugin(beta)
    .build(context_with_dynamic_scope_manifest())
    .unwrap();

  run_setup(app);

  assert_eq!(DESERIALIZATIONS.load(Ordering::SeqCst), 7);
}
