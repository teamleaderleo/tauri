// Copyright 2019-2024 Tauri Programme within The Commons Conservancy
// SPDX-License-Identifier: Apache-2.0
// SPDX-License-Identifier: MIT

use std::collections::BTreeMap;

use tauri::ipc::{Origin, RuntimeAuthority};
use tauri_utils::{
  acl::{
    capability::Capability,
    manifest::Manifest,
    resolved::{Resolved, ResolvedCommand},
    Commands, ExecutionContext, Permission, APP_ACL_KEY,
  },
  platform::Target,
};

fn command(context: ExecutionContext, windows: &[&str], webviews: &[&str]) -> ResolvedCommand {
  ResolvedCommand::new(
    context,
    Default::default(),
    windows
      .iter()
      .map(|pattern| pattern.parse().unwrap())
      .collect(),
    webviews
      .iter()
      .map(|pattern| pattern.parse().unwrap())
      .collect(),
    None,
  )
}

fn authority(allowed: Vec<ResolvedCommand>, denied: Vec<ResolvedCommand>) -> RuntimeAuthority {
  let mut allowed_commands = BTreeMap::new();
  allowed_commands.insert("fieldwork".to_string(), allowed);
  let mut denied_commands = BTreeMap::new();
  denied_commands.insert("fieldwork".to_string(), denied);

  RuntimeAuthority::new(
    BTreeMap::new(),
    Resolved {
      allowed_commands,
      denied_commands,
      ..Default::default()
    },
  )
}

fn permission(identifier: &str, allow: &[&str], deny: &[&str]) -> Permission {
  Permission {
    identifier: identifier.to_string(),
    commands: Commands {
      allow: allow.iter().map(|command| command.to_string()).collect(),
      deny: deny.iter().map(|command| command.to_string()).collect(),
    },
    ..Default::default()
  }
}

fn capability(
  identifier: &str,
  local: bool,
  remote: Option<&str>,
  window: &str,
  permission: &str,
) -> Capability {
  serde_json::from_value(serde_json::json!({
    "identifier": identifier,
    "local": local,
    "remote": remote.map(|url| serde_json::json!({ "urls": [url] })),
    "windows": [window],
    "permissions": [permission]
  }))
  .unwrap()
}

fn resolved_authority(allow: Capability, deny: Capability) -> RuntimeAuthority {
  let manifest = Manifest {
    permissions: [
      (
        "allow-fieldwork".to_string(),
        permission("allow-fieldwork", &["fieldwork"], &[]),
      ),
      (
        "deny-fieldwork".to_string(),
        permission("deny-fieldwork", &[], &["fieldwork"]),
      ),
    ]
    .into_iter()
    .collect(),
    ..Default::default()
  };
  let acl = [(APP_ACL_KEY.to_string(), manifest)].into_iter().collect();
  let capabilities = [
    (allow.identifier.clone(), allow),
    (deny.identifier.clone(), deny),
  ]
  .into_iter()
  .collect();
  let resolved = Resolved::resolve(&acl, capabilities, Target::current()).unwrap();

  RuntimeAuthority::new(acl, resolved)
}

#[test]
fn deny_for_other_origin_does_not_block_local_access() {
  let authority = authority(
    vec![command(ExecutionContext::Local, &["main"], &[])],
    vec![command(
      ExecutionContext::Remote {
        url: "https://denied.example/*".parse().unwrap(),
      },
      &["main"],
      &[],
    )],
  );

  assert!(
    authority
      .resolve_access("fieldwork", "main", "main", &Origin::Local)
      .is_some(),
    "deny rule for another origin blocked local access"
  );
}

#[test]
fn deny_for_other_window_does_not_block_main_window() {
  let authority = authority(
    vec![command(ExecutionContext::Local, &["main"], &[])],
    vec![command(ExecutionContext::Local, &["admin"], &[])],
  );

  assert!(
    authority
      .resolve_access("fieldwork", "main", "main", &Origin::Local)
      .is_some(),
    "deny rule for another window blocked main-window access"
  );
}

#[test]
fn matching_deny_still_overrides_matching_allow() {
  let authority = authority(
    vec![command(ExecutionContext::Local, &["main"], &[])],
    vec![command(ExecutionContext::Local, &["main"], &[])],
  );

  assert!(
    authority
      .resolve_access("fieldwork", "main", "main", &Origin::Local)
      .is_none(),
    "matching deny did not override matching allow"
  );
}

#[test]
fn resolved_capability_deny_for_other_origin_does_not_block_local_access() {
  let authority = resolved_authority(
    capability("local-main", true, None, "main", "allow-fieldwork"),
    capability(
      "remote-main-deny",
      false,
      Some("https://denied.example/*"),
      "main",
      "deny-fieldwork",
    ),
  );

  assert!(
    authority
      .resolve_access("fieldwork", "main", "main", &Origin::Local)
      .is_some(),
    "resolved remote capability deny blocked local access"
  );
}

#[test]
fn resolved_capability_deny_for_other_window_does_not_block_main_window() {
  let authority = resolved_authority(
    capability("local-main", true, None, "main", "allow-fieldwork"),
    capability("local-admin-deny", true, None, "admin", "deny-fieldwork"),
  );

  assert!(
    authority
      .resolve_access("fieldwork", "main", "main", &Origin::Local)
      .is_some(),
    "resolved admin-window deny blocked main-window access"
  );
}
