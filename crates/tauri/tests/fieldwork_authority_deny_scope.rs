// Copyright 2019-2024 Tauri Programme within The Commons Conservancy
// SPDX-License-Identifier: Apache-2.0
// SPDX-License-Identifier: MIT

use std::collections::BTreeMap;

use tauri::ipc::{Origin, RuntimeAuthority};
use tauri_utils::acl::{
  resolved::{Resolved, ResolvedCommand},
  ExecutionContext,
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
