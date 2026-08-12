from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    path.write_text(text.replace(old, new, 1))


plugin = Path("crates/tauri/src/plugin.rs")
old_methods = '''  /// Adds a plugin to the store.
  ///
  /// Returns `true` if a plugin with the same name is already in the store.
  pub fn register(&mut self, plugin: Box<dyn Plugin<R>>) -> bool {
    let len = self.store.len();
    self.store.retain(|p| p.name() != plugin.name());
    let result = len != self.store.len();
    self.store.push(plugin);
    result
  }

  /// Removes the plugin with the given name from the store.
  pub fn unregister(&mut self, plugin: &str) -> bool {
    let len = self.store.len();
    self.store.retain(|p| p.name() != plugin);
    len != self.store.len()
  }

  /// Initializes the given plugin.
  pub(crate) fn initialize(
    &self,
    plugin: &mut Box<dyn Plugin<R>>,
    app: &AppHandle<R>,
    config: &PluginConfig,
  ) -> crate::Result<()> {
    initialize(plugin, app, config)
  }
'''
new_methods = '''  /// Adds a plugin to the store.
  ///
  /// Returns `true` if a plugin with the same name is already in the store.
  pub fn register(&mut self, plugin: Box<dyn Plugin<R>>) -> bool {
    self.register_replacing(plugin).is_some()
  }

  pub(crate) fn register_replacing(
    &mut self,
    plugin: Box<dyn Plugin<R>>,
  ) -> Option<Box<dyn Plugin<R>>> {
    let replaced = self
      .store
      .iter()
      .position(|p| p.name() == plugin.name())
      .map(|index| self.store.remove(index));
    self.store.push(plugin);
    replaced
  }

  /// Removes the plugin with the given name from the store.
  pub fn unregister(&mut self, plugin: &str) -> bool {
    self.unregister_owned(plugin).is_some()
  }

  pub(crate) fn unregister_owned(&mut self, plugin: &str) -> Option<Box<dyn Plugin<R>>> {
    self
      .store
      .iter()
      .position(|p| p.name() == plugin)
      .map(|index| self.store.remove(index))
  }

  /// Initializes the given plugin.
  pub(crate) fn initialize(
    &self,
    plugin: &mut Box<dyn Plugin<R>>,
    app: &AppHandle<R>,
    config: &PluginConfig,
  ) -> crate::Result<()> {
    Self::initialize_plugin(plugin, app, config)
  }

  pub(crate) fn initialize_plugin(
    plugin: &mut Box<dyn Plugin<R>>,
    app: &AppHandle<R>,
    config: &PluginConfig,
  ) -> crate::Result<()> {
    initialize(plugin, app, config)
  }
'''
replace_once(plugin, old_methods, new_methods, "plugin store operations")

app = Path("crates/tauri/src/app.rs")
old_app = '''  pub fn plugin_boxed(&self, mut plugin: Box<dyn Plugin<R>>) -> crate::Result<()> {
    let mut store = self.manager().plugins.lock().unwrap();
    store.initialize(&mut plugin, self, &self.config().plugins)?;
    store.register(plugin);

    Ok(())
  }
'''
new_app = '''  pub fn plugin_boxed(&self, mut plugin: Box<dyn Plugin<R>>) -> crate::Result<()> {
    PluginStore::initialize_plugin(&mut plugin, self, &self.config().plugins)?;
    let replaced = {
      let mut store = self.manager().plugins.lock().unwrap();
      store.register_replacing(plugin)
    };
    drop(replaced);

    Ok(())
  }
'''
replace_once(app, old_app, new_app, "dynamic plugin registration")

old_remove = '''  pub fn remove_plugin(&self, plugin: &str) -> bool {
    self.manager().plugins.lock().unwrap().unregister(plugin)
  }
'''
new_remove = '''  pub fn remove_plugin(&self, plugin: &str) -> bool {
    let removed = {
      let mut store = self.manager().plugins.lock().unwrap();
      store.unregister_owned(plugin)
    };
    removed.is_some()
  }
'''
replace_once(app, old_remove, new_remove, "dynamic plugin removal")
