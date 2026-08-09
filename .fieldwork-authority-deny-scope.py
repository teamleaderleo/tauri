from pathlib import Path

path = Path("crates/tauri/src/ipc/authority.rs")
text = path.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    text = text.replace(old, new, 1)


origin_impl = '''impl Origin {
  fn matches(&self, context: &ExecutionContext) -> bool {
    match (self, context) {
      (Self::Local, ExecutionContext::Local) => true,
      (Self::Remote { url }, ExecutionContext::Remote { url: url_pattern }) => {
        url_pattern.test(url)
      }
      _ => false,
    }
  }
}
'''

replace_once(
    origin_impl,
    origin_impl
    + '''
fn resolved_command_matches(
  command: &ResolvedCommand,
  window: &str,
  webview: &str,
  origin: &Origin,
) -> bool {
  origin.matches(&command.context)
    && (command.webviews.iter().any(|w| w.matches(webview))
      || command.windows.iter().any(|w| w.matches(window)))
}
''',
    "shared matcher insertion",
)

old_debug = '''    if let Some(resolved) = self.denied_commands.get(&command) {
      format!(
        "{command_pretty_name} explicitly denied on origin {origin}\\n\\nreferenced by: {}",
        print_references(resolved)
      )
    } else {
      let command_matches = self.allowed_commands.get(&command);

      if let Some(resolved) = self.allowed_commands.get(&command) {
        let resolved_matching_origin = resolved
          .iter()
          .filter(|cmd| origin.matches(&cmd.context))
          .collect::<Vec<&ResolvedCommand>>();
        if resolved_matching_origin
          .iter()
          .any(|cmd| cmd.webviews.iter().any(|w| w.matches(webview)))
          || resolved_matching_origin
            .iter()
            .any(|cmd| cmd.windows.iter().any(|w| w.matches(window)))
        {
          "allowed".to_string()
'''

new_debug = '''    let matching_denied = self.denied_commands.get(&command).and_then(|resolved| {
      let matching = resolved
        .iter()
        .filter(|cmd| resolved_command_matches(cmd, window, webview, origin))
        .cloned()
        .collect::<Vec<_>>();
      (!matching.is_empty()).then_some(matching)
    });

    if let Some(resolved) = matching_denied {
      format!(
        "{command_pretty_name} explicitly denied on window \\"{window}\\", webview \\"{webview}\\", origin {origin}\\n\\nreferenced by: {}",
        print_references(&resolved)
      )
    } else {
      let command_matches = self.allowed_commands.get(&command);

      if let Some(resolved) = self.allowed_commands.get(&command) {
        if resolved
          .iter()
          .any(|cmd| resolved_command_matches(cmd, window, webview, origin))
        {
          "allowed".to_string()
'''

replace_once(old_debug, new_debug, "debug access matcher")

old_resolve = '''    if self
      .denied_commands
      .get(command)
      .map(|resolved| resolved.iter().any(|cmd| origin.matches(&cmd.context)))
      .is_some()
    {
      None
    } else {
      self.allowed_commands.get(command).and_then(|resolved| {
        let resolved_cmds = resolved
          .iter()
          .filter(|cmd| {
            origin.matches(&cmd.context)
              && (cmd.webviews.iter().any(|w| w.matches(webview))
                || cmd.windows.iter().any(|w| w.matches(window)))
          })
          .cloned()
          .collect::<Vec<_>>();
'''

new_resolve = '''    if self
      .denied_commands
      .get(command)
      .is_some_and(|resolved| {
        resolved
          .iter()
          .any(|cmd| resolved_command_matches(cmd, window, webview, origin))
      })
    {
      None
    } else {
      self.allowed_commands.get(command).and_then(|resolved| {
        let resolved_cmds = resolved
          .iter()
          .filter(|cmd| resolved_command_matches(cmd, window, webview, origin))
          .cloned()
          .collect::<Vec<_>>();
'''

replace_once(old_resolve, new_resolve, "runtime access matcher")

path.write_text(text)
