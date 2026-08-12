from pathlib import Path

path = Path("crates/tauri-build/src/lib.rs")
text = path.read_text()

if "mod fieldwork_resource_target_collision" in text:
    raise SystemExit("fieldwork resource collision tests already present")

text += r'''

#[cfg(test)]
mod fieldwork_resource_target_collision {
  use super::*;
  use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
  };

  fn temp_root(name: &str) -> PathBuf {
    let unique = SystemTime::now()
      .duration_since(UNIX_EPOCH)
      .unwrap()
      .as_nanos();
    std::env::temp_dir().join(format!(
      "tauri-fieldwork-{name}-{}-{unique}",
      std::process::id()
    ))
  }

  fn resource_map(entries: &[(&Path, &str)]) -> HashMap<String, String> {
    entries
      .iter()
      .map(|(source, target)| {
        (
          source.to_string_lossy().into_owned(),
          (*target).to_string(),
        )
      })
      .collect()
  }

  #[test]
  fn cross_mapping_duplicate_resource_targets_are_rejected() {
    let root = temp_root("resource-cross-collision");
    let output = root.join("out");
    fs::create_dir_all(&output).unwrap();

    let first = root.join("first.txt");
    let second = root.join("second.txt");
    fs::write(&first, b"first").unwrap();
    fs::write(&second, b"second").unwrap();

    let resources = resource_map(&[(&first, "same.txt"), (&second, "same.txt")]);
    let result = copy_resources(ResourcePaths::from_map(&resources, true), &output);

    let _ = fs::remove_dir_all(&root);
    assert!(
      result.is_err(),
      "two distinct source files silently claimed the same final resource target"
    );
  }

  #[test]
  fn distinct_resource_targets_still_copy_successfully() {
    let root = temp_root("resource-distinct-targets");
    let output = root.join("out");
    fs::create_dir_all(&output).unwrap();

    let first = root.join("first.txt");
    let second = root.join("second.txt");
    fs::write(&first, b"first").unwrap();
    fs::write(&second, b"second").unwrap();

    let resources = resource_map(&[(&first, "first.txt"), (&second, "second.txt")]);
    let result = copy_resources(ResourcePaths::from_map(&resources, true), &output);

    assert!(result.is_ok(), "disjoint final targets should remain valid: {result:?}");
    assert_eq!(fs::read(output.join("first.txt")).unwrap(), b"first");
    assert_eq!(fs::read(output.join("second.txt")).unwrap(), b"second");

    let _ = fs::remove_dir_all(&root);
  }

  #[test]
  fn same_canonical_source_same_target_overlap_remains_valid() {
    let root = temp_root("resource-same-source-overlap");
    let output = root.join("out");
    fs::create_dir_all(&output).unwrap();

    let source = root.join("source.txt");
    fs::write(&source, b"same source").unwrap();
    let source_alias = format!("{}/./source.txt", root.display());
    let resources = HashMap::from([
      (source.to_string_lossy().into_owned(), "same.txt".to_string()),
      (source_alias, "same.txt".to_string()),
    ]);

    let result = copy_resources(ResourcePaths::from_map(&resources, true), &output);

    assert!(
      result.is_ok(),
      "the same canonical source claiming the same target should remain valid: {result:?}"
    );
    assert_eq!(fs::read(output.join("same.txt")).unwrap(), b"same source");

    let _ = fs::remove_dir_all(&root);
  }

  #[test]
  fn flattened_glob_same_basename_collision_is_rejected() {
    let root = temp_root("resource-glob-collision");
    let docs_a = root.join("docs/a");
    let docs_b = root.join("docs/b");
    let output = root.join("out");
    fs::create_dir_all(&docs_a).unwrap();
    fs::create_dir_all(&docs_b).unwrap();
    fs::create_dir_all(&output).unwrap();
    fs::write(docs_a.join("readme.md"), b"a").unwrap();
    fs::write(docs_b.join("readme.md"), b"b").unwrap();

    let pattern = root.join("docs/**/*.md").to_string_lossy().into_owned();
    let resources = HashMap::from([(pattern, "website-docs/".to_string())]);
    let result = copy_resources(ResourcePaths::from_map(&resources, true), &output);

    let _ = fs::remove_dir_all(&root);
    assert!(
      result.is_err(),
      "flattened glob silently allowed two distinct files to claim website-docs/readme.md"
    );
  }
}
'''

path.write_text(text)
