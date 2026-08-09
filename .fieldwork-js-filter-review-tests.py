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
    assert!(listeners.has_js_listener(event.as_str_event(), |_| true));
  }

  #[test]
  fn js_filter_reentrant_unlisten_affects_next_dispatch() {
    use std::sync::{
      atomic::{AtomicUsize, Ordering},
      Arc,
    };

    let app = crate::test::mock_app();
    let webview_window =
      crate::WebviewWindowBuilder::new(&app, "filter-unlisten-reentry", Default::default())
        .build()
        .unwrap();
    let webview = webview_window.as_ref();

    let listeners = Listeners::default();
    let listeners_from_filter = listeners.clone();
    let event = crate::EventName::new("filter-unlisten-reentry".to_owned()).unwrap();
    let event_from_filter = event.clone();
    let id = listeners.next_event_id();
    listeners.listen_js(
      event.as_str_event(),
      webview.label(),
      EventTarget::webview(webview.label()),
      id,
    );
    let args = EmitArgs::new(event.as_str_event(), &()).unwrap();
    let calls = Arc::new(AtomicUsize::new(0));
    let calls_from_filter = calls.clone();

    listeners
      .emit_js_filter(
        std::iter::once(webview),
        &args,
        Some(move |_: &EventTarget| {
          calls_from_filter.fetch_add(1, Ordering::SeqCst);
          listeners_from_filter.unlisten_js(event_from_filter.as_str_event(), id);
          true
        }),
      )
      .unwrap();

    assert_eq!(calls.load(Ordering::SeqCst), 1);
    assert!(!listeners.has_js_listener(event.as_str_event(), |_| true));

    listeners
      .emit_js_filter(
        std::iter::once(webview),
        &args,
        Some(|_: &EventTarget| -> bool {
          panic!("removed listener was filtered again on a later dispatch")
        }),
      )
      .unwrap();
  }

  #[test]
  fn js_filter_reentrant_listen_affects_next_dispatch() {
    use std::sync::{
      atomic::{AtomicUsize, Ordering},
      Arc,
    };

    let app = crate::test::mock_app();
    let webview_window =
      crate::WebviewWindowBuilder::new(&app, "filter-listen-reentry", Default::default())
        .build()
        .unwrap();
    let webview = webview_window.as_ref();
    let webview_label = webview.label().to_string();

    let listeners = Listeners::default();
    let listeners_from_filter = listeners.clone();
    let event = crate::EventName::new("filter-listen-reentry".to_owned()).unwrap();
    let event_from_filter = event.clone();
    let id = listeners.next_event_id();
    listeners.listen_js(
      event.as_str_event(),
      &webview_label,
      EventTarget::webview(&webview_label),
      id,
    );
    let args = EmitArgs::new(event.as_str_event(), &()).unwrap();

    let first_calls = Arc::new(AtomicUsize::new(0));
    let first_calls_from_filter = first_calls.clone();
    let webview_label_from_filter = webview_label.clone();
    listeners
      .emit_js_filter(
        std::iter::once(webview),
        &args,
        Some(move |_: &EventTarget| {
          first_calls_from_filter.fetch_add(1, Ordering::SeqCst);
          let new_id = listeners_from_filter.next_event_id();
          listeners_from_filter.listen_js(
            event_from_filter.as_str_event(),
            &webview_label_from_filter,
            EventTarget::webview(&webview_label_from_filter),
            new_id,
          );
          true
        }),
      )
      .unwrap();
    assert_eq!(first_calls.load(Ordering::SeqCst), 1);

    let second_calls = Arc::new(AtomicUsize::new(0));
    let second_calls_from_filter = second_calls.clone();
    listeners
      .emit_js_filter(
        std::iter::once(webview),
        &args,
        Some(move |_: &EventTarget| {
          second_calls_from_filter.fetch_add(1, Ordering::SeqCst);
          true
        }),
      )
      .unwrap();
    assert_eq!(second_calls.load(Ordering::SeqCst), 2);
  }
'''
insert_once(listener, listener_marker, listener_tests, "listener regressions")

manager = Path("crates/tauri/src/manager/mod.rs")
manager_marker = """  use super::AppManager;
"""
manager_tests = r'''

  #[test]
  fn app_emit_filter_can_reenter_webview_lookup() {
    use crate::sealed::ManagerBase;

    let app = crate::test::mock_app();
    let webview_window =
      crate::WebviewWindowBuilder::new(&app, "filter-webview-reentry", Default::default())
        .build()
        .unwrap();
    let webview = webview_window.as_ref();
    let manager = app.handle().manager();

    let event = crate::EventName::new("filter-webview-reentry".to_owned()).unwrap();
    let id = manager.listeners.next_event_id();
    manager.listeners.listen_js(
      event.as_str_event(),
      webview.label(),
      crate::EventTarget::webview(webview.label()),
      id,
    );

    manager
      .emit_filter(
        event.as_str_event(),
        super::EmitPayload::Serialize(&()),
        |_: &crate::EventTarget| manager.get_webview(webview.label()).is_some(),
      )
      .unwrap();
  }

  #[test]
  fn app_emit_filter_string_payload_can_reenter_webview_lookup() {
    use crate::sealed::ManagerBase;

    let app = crate::test::mock_app();
    let webview_window = crate::WebviewWindowBuilder::new(
      &app,
      "filter-webview-string-reentry",
      Default::default(),
    )
    .build()
    .unwrap();
    let webview = webview_window.as_ref();
    let manager = app.handle().manager();

    let event = crate::EventName::new("filter-webview-string-reentry".to_owned()).unwrap();
    let id = manager.listeners.next_event_id();
    manager.listeners.listen_js(
      event.as_str_event(),
      webview.label(),
      crate::EventTarget::webview(webview.label()),
      id,
    );

    manager
      .emit_filter(
        event.as_str_event(),
        super::EmitPayload::<()>::Str("{}".to_string()),
        |_: &crate::EventTarget| manager.get_webview(webview.label()).is_some(),
      )
      .unwrap();
  }
'''
insert_once(manager, manager_marker, manager_tests, "manager regressions")
