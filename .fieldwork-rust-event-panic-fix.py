from pathlib import Path

path = Path("crates/tauri/src/event/listener.rs")
text = path.read_text()

old = '''  pub(crate) fn emit_filter<F>(&self, emit_args: EmitArgs, filter: Option<F>) -> crate::Result<()>
  where
    F: Fn(&EventTarget) -> bool,
  {
    let mut maybe_pending = false;

    match self.inner.handlers.try_lock() {
      Err(_) => self.insert_pending(Pending::Emit(emit_args)),
      Ok(lock) => {
        if let Some(handlers) = lock.get(&emit_args.event) {
          let handlers = handlers.iter();
          let handlers = handlers.filter(|(_, h)| match_any_or_filter(&h.target, &filter));
          for (&id, Handler { callback, .. }) in handlers {
            maybe_pending = true;
            (callback)(Event::new(id, emit_args.payload.clone()))
          }
        }
      }
    }

    if maybe_pending {
      self.flush_pending()?;
    }

    Ok(())
  }
'''

new = '''  pub(crate) fn emit_filter<F>(&self, emit_args: EmitArgs, filter: Option<F>) -> crate::Result<()>
  where
    F: Fn(&EventTarget) -> bool,
  {
    let mut maybe_pending = false;
    let mut dispatch_panic = None;

    match self.inner.handlers.try_lock() {
      Err(_) => self.insert_pending(Pending::Emit(emit_args)),
      Ok(lock) => {
        if let Some(handlers) = lock.get(&emit_args.event) {
          let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let handlers = handlers.iter();
            let handlers = handlers.filter(|(_, h)| match_any_or_filter(&h.target, &filter));
            for (&id, Handler { callback, .. }) in handlers {
              maybe_pending = true;
              (callback)(Event::new(id, emit_args.payload.clone()))
            }
          }));
          if let Err(payload) = result {
            dispatch_panic = Some(payload);
          }
        }
      }
    }

    if maybe_pending || dispatch_panic.is_some() {
      self.flush_pending()?;
    }
    if let Some(payload) = dispatch_panic {
      std::panic::resume_unwind(payload);
    }

    Ok(())
  }
'''

count = text.count(old)
if count != 1:
  raise SystemExit(f"emit_filter candidate: expected one source match, found {count}")
path.write_text(text.replace(old, new, 1))
