from pathlib import Path

path = Path("crates/tauri/src/event/listener.rs")
text = path.read_text()
marker = '''  // dummy event handler function
'''
test = r'''  #[test]
  fn rust_filter_panic_flushes_pending_before_resuming() {
    use std::{
      panic::{catch_unwind, AssertUnwindSafe},
      sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
      },
    };

    let listeners = Listeners::default();
    let event = crate::EventName::new("filter-panic".to_owned()).unwrap();
    listeners.listen(event.clone(), EventTarget::App, |_| {});

    let later_event = crate::EventName::new("after-filter-panic".to_owned()).unwrap();
    let later_event_from_filter = later_event.clone();
    let delivered = Arc::new(AtomicBool::new(false));
    let delivered_from_filter = delivered.clone();
    let listeners_from_filter = listeners.clone();

    let result = catch_unwind(AssertUnwindSafe(|| {
      let _ = listeners.emit_filter(
        EmitArgs::new(event.as_str_event(), &()).unwrap(),
        Some(move |_: &EventTarget| -> bool {
          let delivered = delivered_from_filter.clone();
          listeners_from_filter.listen(
            later_event_from_filter.clone(),
            EventTarget::Any,
            move |_| delivered.store(true, Ordering::SeqCst),
          );
          panic!("intentional Rust event filter panic");
        }),
      );
    }));

    assert!(result.is_err(), "filter panic must remain observable");
    listeners
      .emit(EmitArgs::new(later_event.as_str_event(), &()).unwrap())
      .unwrap();
    assert!(
      delivered.load(Ordering::SeqCst),
      "pending listener was not flushed before filter panic resumed"
    );
  }

'''
count = text.count(marker)
if count != 1:
  raise SystemExit(f"test insertion: expected one marker, found {count}")
path.write_text(text.replace(marker, test + marker, 1))
