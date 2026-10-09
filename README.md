# Fulton Steamers Football Scoreboard

## GAME NIGHT QUICK START (Mac mini + OBS)
1. Double-click **Start Scoreboard.command**. (The first time, right-click it, choose **Open**, then click **Open** again.) Leave the Terminal window open.
2. The controller opens at http://localhost:8765/control/ and the badge should say **● LIVE (Mac server)**.
3. In OBS, add a **Browser** source with the URL `http://localhost:8765/show/?bg=transparent`, width **1920**, and height **1080**.
4. A phone or iPad on the same Wi-Fi can also control the scoreboard. Use the address printed in the Terminal window.

Scores are saved in `state.json`, so restarting the server keeps the game.

A Fox NFL–style score bug with a separate controller, built as static files that are hosted free on GitHub Pages.

| Page | URL |
|---|---|
| Scoreboard (display / OBS) | `https://<you>.github.io/<repo>/show/` |
| Controller (phone, tablet, laptop) | `https://<you>.github.io/<repo>/control/` |

## Show page options
- `?bg=field`: default, a stadium background with the matchup shown large
- `?bg=transparent`: for an OBS **Browser Source** (1920×1080)
- `?bg=green`: for chroma key
- `?bg=dark`: plain dark background
- `?game=week7`: run a separate scoreboard (use the same value on `/control`)

## 1. Put it on GitHub Pages
1. Create a new public repo on GitHub, for example `fulton-scoreboard`.
2. Upload every file in this folder, including the hidden `.nojekyll` file.
3. Go to the repo's **Settings → Pages**, choose **Deploy from a branch**, then select `main` and `/ (root)`.
4. After about a minute, the site is at `https://<you>.github.io/fulton-scoreboard/`.

**Custom domain** (like `www.fultonscoreboard.com`): add the domain in **Settings → Pages → Custom domain**, then point a `CNAME` DNS record at `<you>.github.io`.

## 2. Turn on live sync: Google Apps Script (recommended)
1. Go to https://script.google.com and click **New project**.
2. Delete the starter code, then paste in everything from `apps-script/Code.gs`. Save.
3. Click **Deploy → New deployment**. For the type, click the gear and choose **Web app**.
   - Execute as: **Me**
   - Who has access: **Anyone**
4. Click **Deploy**, then **Authorize access** and allow it.
5. Copy the **Web app URL** (it ends in `/exec`) and paste it into `js/config.js` as `appsScriptUrl: "…/exec"`.
6. Commit. When the controller badge says **● LIVE (Google)**, sync is working.

Note: uploaded logos are only kept for 6 hours in Apps Script mode. Put logo files in `assets/` instead.

## 2b. Alternative: Firebase
Without this step, the controller and the scoreboard only sync when both are open in the **same browser on the same computer**.

1. Go to https://console.firebase.google.com and click **Add project** (it's free and you can turn off Analytics).
2. Go to **Build → Realtime Database → Create database**, pick any location, and choose **Start in test mode**.
3. Open **Rules** and paste the following, then click **Publish**:
   ```json
   { "rules": { "scoreboards": { "$game": { ".read": true, ".write": true } } } }
   ```
4. Open **Project settings** (the gear icon), go to **Your apps → Web (</>)**, register the app, and copy the `firebaseConfig` object.
5. Paste that config into `js/config.js` as the value of `firebase:`, then commit the change.

The badge at the top of the controller shows **● LIVE (Firebase)** when sync is working.

> Note: anyone who knows the controller URL can change the score. Don't post the `/control` link publicly.

## Controller tips
- **Space** starts and stops the game clock. **F** toggles the flag.
- **TD / FG / Safety / PAT / 2-PT** add points and play a banner in that team's colors.
- **Use TO** stops the clock, removes one timeout pip, and shows a TIMEOUT banner.
- Choosing **3RD** quarter resets both teams to 3 timeouts. Changing quarters resets the clock to the quarter length (default 12:00).
- Under one minute, the clock shows tenths of a second.
- **Team & game setup** (at the bottom) sets names, abbreviations, records, colors, and logos. You can upload an image or paste a URL.

## Logos
`assets/steamers.png` and `assets/morrison.png` are the team logos, with the white backgrounds removed. To use a different logo, replace the file or upload a new one from the controller.

## Run locally
```bash
python3 -m http.server 8765
```
Then open http://localhost:8765/control/ and http://localhost:8765/show/ in the same browser.
