from pathlib import Path


def insert_once(path: Path, marker: str, insertion: str, label: str) -> None:
    text = path.read_text()
    count = text.count(marker)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one marker, found {count}")
    path.write_text(text.replace(marker, marker + insertion, 1))


listener = Path("crates/tauri/src/event/listener.rs")
listener_marker = """#[cfg(test)]
mod test {
  use super::*;
  use crate::event::EventTarget;
  use proptest::prelude::*;
"""
listener_tests = r'''

  #[test]
  fn js_filter_panic_does_not_poison_listener_registry() {
    use std::panic::{catch_unwind, AssertUnwindSafe};

    let app = crate::test::mock_app();
    let webview_window = crate::WebviewWindowBuilder::new(&app, "filter-panic", Default::default())
      .build()
      .unwrap();
    let webview = webview_window.as_ref();

    let listeners = Listeners::default();
    let event = crate::EventName::new("filter-panic".to_owned()).unwrap();
    let id = listeners.next_event_id();
    listeners.listen_js(
      event.as_str_event(),
      webview.label(),
      EventTarget::webview(webview.label()),
      id,
    );
    let args = EmitArgs::new(event.as_str_event(), &()).unwrap();

    let first = catch_unwind(AssertUnwindSafe(|| {
      let _ = listeners.emit_js_filter(
        std::iter::once(webview),
        &args,
        Some(|_: &EventTarget| -> bool {
          panic!("intentional JS listener filter panic");
        }),
      );
    }));
    assert!(first.is_err(), "filter panic must still reach the caller");

    let registry_read = catch_unwind(AssertUnwindSafe(|| {
      listeners.has_js_listener(event.as_str_event(), |_| true)
    }));
    assert!(
      matches!(registry_read, Ok(true)),
      "JS listener registry was poisoned by filter panic"
    );
  }

  #[test]
  fn js_filter_predicate_runs_without_js_listener_registry_lock() {
    use std::sync::{
      atomic::{AtomicBool, Ordering},
      Arc,
    };

    let app = crate::test::mock_app();
    let webview_window = crate::WebviewWindowBuilder::new(&app, "filter-lock", Default::default())
      .build()
      .unwrap();
    let webview = webview_window.as_ref();

    let listeners = Listeners::default();
    let listeners_from_filter = listeners.clone();
    let event = crate::EventName::new("filter-lock".to_owned()).unwrap();
    let id = listeners.next_event_id();
    listeners.listen_js(
      event.as_str_event(),
      webview.label(),
      EventTarget::webview(webview.label()),
      id,
    );
    let args = EmitArgs::new(event.as_str_event(), &()).unwrap();

    let lock_was_available = Arc::new(AtomicBool::new(false));
    let lock_was_available_from_filter = lock_was_available.clone();

    listeners
      .emit_js_filter(
        std::iter::once(webview),
        &args,
        Some(move |_: &EventTarget| {
          lock_was_available_from_filter.store(
            listeners_from_filter.inner.js_event_listeners.try_lock().is_ok(),
            Ordering::SeqCst,
          );
          true
        }),
      )
      .unwrap();

    assert!(
      lock_was_available.load(Ordering::SeqCst),
      "JS filter predicate ran while the JS listener registry mutex was held"
    );
  }
'''
insert_once(listener, listener_marker, listener_tests, "listener test insertion")

manager = Path("crates/tauri/src/manager/mod.rs")
manager_marker = """  use super::AppManager;
"""
manager_test = r'''

  #[test]
  fn app_emit_filter_predicate_runs_without_webview_store_lock() {
    use crate::sealed::ManagerBase;
    use std::sync::{
      atomic::{AtomicBool, Ordering},
      Arc,
    };

    let app = crate::test::mock_app();
    let webview_window =
      crate::WebviewWindowBuilder::new(&app, "filter-webview-lock", Default::default())
        .build()
        .unwrap();
    let webview = webview_window.as_ref();
    let manager = app.handle().manager();

    let event = crate::EventName::new("filter-webview-lock".to_owned()).unwrap();
    let id = manager.listeners.next_event_id();
    manager.listeners.listen_js(
      event.as_str_event(),
      webview.label(),
      crate::EventTarget::webview(webview.label()),
      id,
    );

    let lock_was_available = Arc::new(AtomicBool::new(false));
    let lock_was_available_from_filter = lock_was_available.clone();

    manager
      .emit_filter(
        event.as_str_event(),
        super::EmitPayload::Serialize(&()),
        |_: &crate::EventTarget| {
          lock_was_available_from_filter.store(
            manager.webview.webviews.try_lock().is_ok(),
            Ordering::SeqCst,
          );
          true
        },
      )
      .unwrap();

    assert!(
      lock_was_available.load(Ordering::SeqCst),
      "public filter predicate ran while the global webview-store mutex was held"
    );
  }
'''
insert_once(manager, manager_marker, manager_test, "manager test insertion")
