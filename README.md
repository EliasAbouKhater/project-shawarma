# Project Shawarma 🌯

A customized discount game for restaurants and food businesses. Customers spin a gauge to win a discount on their order.

## How It Works

1. Admin configures the discount range (e.g. 5%–40%) and speed
2. Admin uploads logo + background image
3. Customer opens `/game` (no login needed)
4. A car-RPM-style gauge rises — customer taps **STOP** before it crashes
5. Wherever they stop = their discount %. If it crashes before they stop → better luck next time
6. Admin can review all game history at `/admin/history`

## Roles

| Role  | Access |
|-------|--------|
| Admin | `/admin` — settings, branding, history |
| Customer | `/game` — no login required |

## Default Credentials

- Admin password: `admin` (change immediately in Settings)

## Local Setup

```bash
pip install -r requirements.txt
python app.py
# → http://localhost:5003
```

## Deploy on Render (free)

1. Push this folder to a GitHub repo
2. Go to [render.com](https://render.com) → New Web Service → connect repo
3. Render will auto-detect `render.yaml`
4. Deploy → get a free `.onrender.com` URL

> **Note:** Render free tier has ephemeral storage — uploaded images and game history will reset on restart.
> For persistence, upgrade to a paid plan or use an external DB.

## Settings (Admin Panel)

| Setting | Description |
|---------|-------------|
| Shop Name | Displayed on game screen |
| Min Discount % | Gauge starts here |
| Max Discount % | Gauge ceiling |
| Gauge Speed (sec) | How long the full sweep takes |
| Logo | Shown at top of game screen |
| Background | Full-screen behind the gauge |

## File Structure

```
project-shawarma/
├── app.py              # Flask app (all routes + logic)
├── requirements.txt
├── render.yaml         # Render.com deployment config
├── shawarma.db         # SQLite DB (auto-created)
├── static/uploads/     # Uploaded logo + background
└── templates/
    ├── admin_login.html
    ├── admin_dashboard.html
    ├── admin_history.html
    └── game.html
```
