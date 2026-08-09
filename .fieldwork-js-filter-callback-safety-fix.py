from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    path.write_text(text.replace(old, new, 1))


listener = Path("crates/tauri/src/event/listener.rs")
old_listener = '''  pub(crate) fn emit_js_filter<'a, R, I, F>(
    &self,
    mut webviews: I,
    emit_args: &EmitArgs,
    filter: Option<F>,
  ) -> crate::Result<()>
  where
    R: Runtime,
    I: Iterator<Item = &'a Webview<R>>,
    F: Fn(&EventTarget) -> bool,
  {
    let event = &emit_args.event;
    let js_listeners = self.inner.js_event_listeners.lock().unwrap();
    webviews.try_for_each(|webview| {
      if let Some(handlers) = js_listeners.get(webview.label()).and_then(|s| s.get(event)) {
        let ids = handlers
          .iter()
          .filter(|handler| match_any_or_filter(&handler.target, &filter))
          .map(|handler| handler.id)
          .collect::<Vec<_>>();
        webview.emit_js(emit_args, &ids)?;
      }

      Ok(())
    })
  }
'''
new_listener = '''  pub(crate) fn emit_js_filter<'a, R, I, F>(
    &self,
    webviews: I,
    emit_args: &EmitArgs,
    filter: Option<F>,
  ) -> crate::Result<()>
  where
    R: Runtime,
    I: Iterator<Item = &'a Webview<R>>,
    F: Fn(&EventTarget) -> bool,
  {
    let event = &emit_args.event;
    let webviews_and_handlers = {
      let js_listeners = self.inner.js_event_listeners.lock().unwrap();
      webviews
        .map(|webview| {
          let handlers = js_listeners
            .get(webview.label())
            .and_then(|events| events.get(event))
            .map(|handlers| handlers.iter().cloned().collect::<Vec<_>>())
            .unwrap_or_default();
          (webview, handlers)
        })
        .collect::<Vec<_>>()
    };

    for (webview, handlers) in webviews_and_handlers {
      let ids = handlers
        .iter()
        .filter(|handler| match_any_or_filter(&handler.target, &filter))
        .map(|handler| handler.id)
        .collect::<Vec<_>>();
      if !handlers.is_empty() {
        webview.emit_js(emit_args, &ids)?;
      }
    }

    Ok(())
  }
'''
replace_once(listener, old_listener, new_listener, "listener snapshot")

manager = Path("crates/tauri/src/manager/mod.rs")
old_manager = '''    let listeners = self.listeners();

    listeners.emit_js_filter(
      self.webview.webviews_lock().values(),
      &emit_args,
      Some(&filter),
    )?;

    listeners.emit_filter(emit_args, Some(filter))?;
'''
new_manager = '''    let listeners = self.listeners();
    let webviews = self
      .webview
      .webviews_lock()
      .values()
      .cloned()
      .collect::<Vec<_>>();

    listeners.emit_js_filter(webviews.iter(), &emit_args, Some(&filter))?;

    listeners.emit_filter(emit_args, Some(filter))?;
'''
replace_once(manager, old_manager, new_manager, "webview snapshot")
