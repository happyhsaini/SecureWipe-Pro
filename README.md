# SecureWipe Pro

This is now a standalone local version of the recovered SecureWipe Pro app.

What works locally:

- Dashboard UI
- Data wipe form submission
- Operations history
- Active operations panel
- Local JSON-backed storage
- Automatic progress simulation from pending to running to completed

Project structure:

- `app.py` - Flask app and local API
- `data/operations.json` - persisted operations store
- `templates/index.html` - app shell
- `static/assets/*` - recovered frontend bundle

Run locally:

```powershell
pip install -r requirements.txt
python app.py
```

Open:

- `http://127.0.0.1:5000`
