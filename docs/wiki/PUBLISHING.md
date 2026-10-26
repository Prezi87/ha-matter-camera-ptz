# Publishing the GitHub Wiki from versioned source

GitHub Wiki is enabled in this project, but it is a **separate Git repository**, not the main `docs/wiki` folder. The source-of-truth pages live in `docs/wiki/*.md` for code review and version control.

## One-time Wiki initialization

If the Wiki is still empty, open **https://github.com/Prezi87/ha-matter-camera-ptz/wiki** and use **Create the first page** to create a page titled `Home` with temporary content (for example `Wiki initializing`). Save it. This creates the separate `.wiki.git` repository.

## Publish reviewed pages

On a computer with Git and repository write access (HTTPS token or configured SSH):

```bash
git clone https://github.com/Prezi87/ha-matter-camera-ptz.git
git clone https://github.com/Prezi87/ha-matter-camera-ptz.wiki.git
cp ha-matter-camera-ptz/docs/wiki/*.md ha-matter-camera-ptz.wiki/
cd ha-matter-camera-ptz.wiki
git add .
git commit -m "docs: publish Matter Camera PTZ v0.3.1 wiki"
git push origin master
```

If the Wiki repository default branch is different, push its actual current branch rather than assuming `master`. Run `git branch --show-current` to check. Commit only intended changed pages; avoid `git add .` if the Wiki contains unrelated material.

Verify `Home`, `Installation`, `Lovelace-Card`, `Privacy-and-PTZ`, `Offline-G350-and-Networking`, `Troubleshooting` and `FAQ` in the Wiki navigation.

If `git clone ...wiki.git` fails, first confirm **Settings → General → Features → Wikis** is enabled and the first Wiki page has been created. Publishing requires credentials with write access to the Wiki repository.

> The GitHub connector available during document preparation could change the main repository but did not provide GitHub Wiki Git push operations. Therefore this guide does not claim those pages have been published to the separate Wiki until verified.
