const repo = 'https://github.com/sidneykanoti/LNMTLWebToEbook';
export const patterns = {
  windows: /-windows-x64\.exe$/i,
  'mac-arm': /-macos-arm64\.dmg$/i,
  'mac-intel': /-macos-x64\.dmg$/i,
  linux: /-linux-x64\.tar\.gz$/i,
  'linux-deb': /-linux-x64\.deb$/i,
};
export function selectAsset(assets, platform) {
  return assets.find(asset => patterns[platform]?.test(asset.name));
}
export async function onRequestGet({ params, request }) {
  if (!patterns[params.platform]) return new Response('Unknown platform', { status: 404 });
  try {
    const response = await fetch('https://api.github.com/repos/sidneykanoti/LNMTLWebToEbook/releases/latest', {
      headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'LNMTL-Website' },
      cf: { cacheTtl: 60, cacheEverything: true },
    });
    if (!response.ok) throw new Error('Release unavailable');
    const release = await response.json();
    const asset = selectAsset(release.assets ?? [], params.platform);
    if (!asset || !asset.browser_download_url.startsWith(`${repo}/releases/download/`)) throw new Error('Asset unavailable');
    return new Response(null, { status: 302, headers: { Location: asset.browser_download_url, 'Cache-Control': 'no-store' } });
  } catch {
    return new Response(null, { status: 302, headers: { Location: new URL('/?download=unavailable#download', request.url).href, 'Cache-Control': 'no-store' } });
  }
}
