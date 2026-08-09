from pathlib import Path

path = Path("crates/tauri/src/app.rs")
text = path.read_text()

if "mod fieldwork_plugin_store_reentrancy" in text:
    raise SystemExit("fieldwork plugin store tests already present")

text += r'''

#[cfg(test)]
mod fieldwork_plugin_store_reentrancy {
  use super::*;
  use crate::plugin::Builder as PluginBuilder;
  use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
  };

  #[test]
  fn dynamic_plugin_setup_runs_without_plugin_store_lock() {
    let app = crate::test::mock_app();
    let lock_was_available = Arc::new(AtomicBool::new(false));
    let lock_was_available_clone = lock_was_available.clone();

    let plugin = PluginBuilder::new("fieldwork-dynamic-setup")
      .setup(move |app, _api| {
        lock_was_available_clone.store(
          app.manager.plugins.try_lock().is_ok(),
          Ordering::SeqCst,
        );
        Ok(())
      })
      .build();

    app.handle().plugin(plugin).unwrap();

    assert!(
      lock_was_available.load(Ordering::SeqCst),
      "dynamic plugin setup ran while the global plugin-store mutex was held"
    );
  }

  #[test]
  fn remove_plugin_drops_callback_without_plugin_store_lock() {
    let app = crate::test::mock_app();
    let lock_was_available = Arc::new(AtomicBool::new(false));
    let lock_was_available_clone = lock_was_available.clone();

    let plugin = PluginBuilder::new("fieldwork-remove-drop")
      .on_drop(move |app| {
        lock_was_available_clone.store(
          app.manager.plugins.try_lock().is_ok(),
          Ordering::SeqCst,
        );
      })
      .build();

    app.handle().plugin(plugin).unwrap();
    assert!(app.handle().remove_plugin("fieldwork-remove-drop"));

    assert!(
      lock_was_available.load(Ordering::SeqCst),
      "remove_plugin dropped application callback code while the plugin-store mutex was held"
    );
  }

  #[test]
  fn same_name_replacement_drops_old_plugin_without_store_lock() {
    let app = crate::test::mock_app();
    let lock_was_available = Arc::new(AtomicBool::new(false));
    let lock_was_available_clone = lock_was_available.clone();

    let old_plugin = PluginBuilder::new("fieldwork-replace-drop")
      .on_drop(move |app| {
        lock_was_available_clone.store(
          app.manager.plugins.try_lock().is_ok(),
          Ordering::SeqCst,
        );
      })
      .build();
    let replacement = PluginBuilder::new("fieldwork-replace-drop").build();

    app.handle().plugin(old_plugin).unwrap();
    app.handle().plugin(replacement).unwrap();

    assert!(
      lock_was_available.load(Ordering::SeqCst),
      "same-name registration dropped the replaced plugin while the plugin-store mutex was held"
    );
  }
}
'''

path.write_text(text)
