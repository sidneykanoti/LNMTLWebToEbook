# LNMTL Web to Ebook website

Astro promotional site, with Cloudflare Pages Functions resolving the latest GitHub release downloads at click time. No database or secrets required.

The page presents the app as an independent whole-novel downloader and personal preservation tool for content listed on lnmtl.com. It explains that individual chapters cannot be selected, shows how to disable Sample first, and attributes the shutdown concerns and preservation motivation to the project creator. It does not present those concerns as an official LNMTL announcement.

## Develop

Run `npm install`, then `npm run dev`. Astro's local preview renders the site; `/download/*` handlers run on Cloudflare Pages, or locally using `npx wrangler pages dev dist` after building.

## Verify

`npm test` checks release asset selection and download redirects. `npm run build` produces `dist`.

## Deploy to Cloudflare Pages

Live site: https://lnmtl-web-to-ebook.pages.dev/

The Cloudflare Pages project `lnmtl-web-to-ebook` uses direct upload. The repository-root `.github/workflows/website.yml` checks and builds the site on website changes and deploys pushes to `main`. Pull requests run checks without receiving deployment credentials. Set the repository Actions secret `CLOUDFLARE_API_TOKEN` to a Cloudflare token with Account → Cloudflare Pages → Edit permission, scoped to the account shown in the workflow. Never put the token in source files.

To publish manually from this folder, run `npm run deploy` after signing in with `npx wrangler login`. This uploads both `dist` and the download Functions. The Git integration instructions below apply only to a new project; Cloudflare does not let direct-upload projects switch to built-in Git integration.

Push this folder to a GitHub repository and connect it in Cloudflare Workers & Pages → Create → Pages → Import an existing Git repository.

- Root directory: `website` if this folder is committed in the software repository; leave empty if using a dedicated website repository.
- Build command: `npm run build`
- Build output directory: `dist`
- Node version: 26 (matches the tested local build and GitHub Actions workflow).

Cloudflare deploys the root `functions` directory automatically. Use Git integration or Wrangler, rather than uploading only `dist`, so the download handlers are included.

The repository-root `.github/workflows/website.yml` is the website workflow. Desktop release builds remain in their existing workflow.

Downloads use GitHub's latest stable release endpoint, cached for up to 60 seconds. Filenames can contain any version prefix; platform suffixes must remain `-windows-x64.exe`, `-macos-arm64.dmg`, `-macos-x64.dmg`, `-linux-x64.tar.gz`, or `-linux-x64.deb`. An unavailable file returns visitors to a visible help message with a GitHub Releases link.

Do not change the software's release workflow to deploy this site. The site works independently of desktop builds.
