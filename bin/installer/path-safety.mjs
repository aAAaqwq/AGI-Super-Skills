import * as nativePath from "node:path";
import { lstatSync, realpathSync } from "node:fs";


export function isStrictDescendant(root, candidate, pathApi = nativePath) {
  const resolvedRoot = pathApi.resolve(root);
  const resolvedCandidate = pathApi.resolve(candidate);
  const relativePath = pathApi.relative(resolvedRoot, resolvedCandidate);
  return relativePath !== ""
    && relativePath !== ".."
    && !relativePath.startsWith(`..${pathApi.sep}`)
    && !pathApi.isAbsolute(relativePath);
}

export function isPhysicalStrictDescendant(root, candidate) {
  if (!isStrictDescendant(root, candidate)) return false;
  try {
    const resolvedRoot = nativePath.resolve(root);
    const resolvedCandidate = nativePath.resolve(candidate);
    const rootMetadata = lstatSync(resolvedRoot);
    if (rootMetadata.isSymbolicLink() || !rootMetadata.isDirectory()) return false;
    let cursor = resolvedRoot;
    for (const component of nativePath.relative(resolvedRoot, resolvedCandidate).split(nativePath.sep)) {
      if (!component) continue;
      cursor = nativePath.join(cursor, component);
      if (lstatSync(cursor).isSymbolicLink()) return false;
    }
    return isStrictDescendant(
      realpathSync.native(resolvedRoot),
      realpathSync.native(resolvedCandidate),
    );
  } catch {
    return false;
  }
}
