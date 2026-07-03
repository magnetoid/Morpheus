# richtext frontend (Lexical)

`editor.js` is the source. The committed build artifact
`../static/richtext/lexical-editor.bundle.js` is what production serves — the
Coolify/Python deploy has no Node, so **you must rebuild + commit the bundle
whenever `editor.js` changes**.

## Rebuild

    cd plugins/installed/richtext/frontend
    npm install          # dev-only; node_modules is gitignored
    npm run build        # → ../static/richtext/lexical-editor.bundle.js

Commit both `editor.js` and the regenerated bundle in the same change.
