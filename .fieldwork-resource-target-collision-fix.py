from pathlib import Path

path = Path("crates/tauri-build/src/lib.rs")
text = path.read_text()

old = '''/// Copies resources to a path.
fn copy_resources(resources: ResourcePaths<'_>, path: &Path) -> Result<()> {
  let path = path.canonicalize()?;
  let mut resources = resources.iter();
  for resource in resources.by_ref() {
    let resource = resource?;

    // avoid copying the resource if target is the same as source
    let src = resource.path().canonicalize()?;
    let target = path.join(resource.target());
    if src != target {
      copy_file(src, target)?;
    }
  }

  for path in resources.rerun_if_changed() {
    println!("cargo:rerun-if-changed={}", path.display());
  }

  Ok(())
}
'''

new = '''/// Copies resources to a path.
fn copy_resources(resources: ResourcePaths<'_>, path: &Path) -> Result<()> {
  let path = path.canonicalize()?;
  let mut resources = resources.iter();
  let mut resolved_resources = Vec::new();
  let mut target_owners = HashMap::<PathBuf, PathBuf>::new();

  for resource in resources.by_ref() {
    let resource = resource?;
    let src = resource.path().canonicalize()?;
    let target = path.join(resource.target());

    if let Some(existing_src) = target_owners.get(&target) {
      if existing_src != &src {
        return Err(anyhow::anyhow!(
          "resource target collision: {:?} and {:?} both map to {:?}",
          existing_src,
          src,
          target
        ));
      }
    } else {
      target_owners.insert(target.clone(), src.clone());
    }

    resolved_resources.push((src, target));
  }

  for (src, target) in resolved_resources {
    // avoid copying the resource if target is the same as source
    if src != target {
      copy_file(src, target)?;
    }
  }

  for path in resources.rerun_if_changed() {
    println!("cargo:rerun-if-changed={}", path.display());
  }

  Ok(())
}
'''

count = text.count(old)
if count != 1:
    raise SystemExit(f"copy_resources: expected one source match, found {count}")

path.write_text(text.replace(old, new, 1))
