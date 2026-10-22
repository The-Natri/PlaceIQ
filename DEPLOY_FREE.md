# Deploying PlaceIQ permanently, for free

A step-by-step guide you can follow yourself. **Nothing here has been run for
you, and no account has been created.** Each step needs your own free
accounts. For a temporary link from your laptop, use
`scripts/share.ps1` instead: no account, but the link only lasts while your
laptop runs it.

**Recommended setup:**
- the app on a **Render free web service**, built from this repo's `Dockerfile`;
- the database on **Neon's free Postgres**.

Neon's free database doesn't expire. Render's free database reportedly does
(see the limits below).

## Know the limits first

Checked in October 2026. Free tiers change, so confirm on the linked pages
before relying on them.

| | Limit | What it means for PlaceIQ |
|---|---|---|
| Render free web service | 512 MB RAM, 0.1 CPU; **spins down after 15 minutes without traffic**; waking takes up to about a minute; 750 free instance-hours a month per workspace; local files are lost on spin-down ([render.com/free](https://render.com/free), [changelog](https://render.com/changelog/free-web-services-now-remain-active-while-receiving-websocket-messages)) | The first visit after a quiet spell is slow (**cold start**). Secrets must be environment variables, not generated files. |
| Render free Postgres | Reported **expiry 30 days** after creation, 256 MB RAM ([third-party summary](https://agentdeals.dev/vendor/render); confirm on Render's pricing page) | That's why Neon is used instead. |
| Neon free Postgres | 0.5 GB storage and 100 compute-hours a month per project; **scales to zero after 5 minutes idle**; compute is suspended until next month if a limit is exceeded ([neon.com/pricing](https://neon.com/pricing)) | PlaceIQ's synthetic data is a few MB. The first query after idling waits a moment while the database wakes. |

**The ML service** (placement probability) is a second container. On Render's
free tier it would need to be a second *public* web service (free plans
can't make it private), with its own cold starts. The simplest free setup
**leaves it out**: the student dashboard then shows that the probability is
unavailable, and everything else works. Optional steps for adding it are at
the end.

## 1. Database on Neon

1. Sign up at <https://neon.com> (free plan, no card).
2. Create a project, for example `placeiq`, in a region near you (Asia Pacific for India).
3. Copy the **connection string** from the dashboard. It looks like
   `postgresql://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`.
   Keep it private.

You don't need to create tables: the app does that on its first start
(`docker/init_db.py` applies `db/schema.sql` and loads the synthetic data).

## 2. Secrets

Generate three random values on your own machine (needs Python):

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(12))"   # ADMIN_PASSWORD
python -c "import secrets; print(secrets.token_urlsafe(12))"   # STUDENT_PASSWORD
```

Keep them in a password manager. Never commit them.

## 3. App on Render

1. Sign up at <https://render.com> with your GitHub account (free plan).
2. **New → Web Service**, connect your GitHub repository, and pick the branch you want to deploy.
3. Settings:
   - **Language / Runtime:** Docker (it finds the `Dockerfile` at the repository root)
   - **Instance type:** Free
   - **Health check path:** `/api/health`
4. **Environment variables** (mark the secret ones as secret):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string (keep `?sslmode=require`) |
   | `JWT_SECRET_KEY` | your generated value |
   | `PUBLIC_MODE` | `1` |
   | `ADMIN_PASSWORD` | your generated value |
   | `STUDENT_PASSWORD` | your generated value |
   | `RATE_LIMIT_IP_HEADER` | `X-Forwarded-For` (Render's proxy sets it; without it every visitor would share one login limit) |
   | `ML_SERVICE_URL` | leave unset unless you add the ML service |

   You don't need `PORT` or `HOST`: Render sets `PORT`, and the image listens
   on `0.0.0.0`.
5. **Create Web Service.** The first deploy builds the image (several
   minutes), then the first start loads the synthetic data (1–3 minutes on
   the free CPU). If the first health check gives up during seeding,
   use **Manual Deploy → Restart**: the data load resumes, because the seed
   starts from scratch whenever it didn't finish.
6. Open the `https://<name>.onrender.com` address Render shows. Log in as
   `tpo@campus.edu` with your `ADMIN_PASSWORD`, or as any seeded student
   with your `STUDENT_PASSWORD`. In public mode the demo passwords
   (`Admin@123`, `Student@123`) don't work, and logins are rate-limited
   (10 attempts per 5 minutes per visitor).

## Optional: the ML service

1. **New → Web Service** again, from the same repository, with **Root
   Directory** `ml-service` (it has its own `Dockerfile`). Free instance.
2. Environment: `DATABASE_URL` = the same Neon string, and `ML_PORT` set to the value of Render's `PORT` (or leave the default and set the service's port to 6000 in its settings).
3. Health check path: `/health`.
4. Once it is live, set `ML_SERVICE_URL` on the app service to its `https://...onrender.com` address and redeploy the app.

It trains the model on every cold start (a few seconds) because free
services lose local files. Its `/predict` endpoint is public in this setup.
It only returns a probability for the numbers sent to it, from a model
trained on synthetic data.

## Costs and cleanup

All of the above is on free plans; none of it asks for a card at the time of
writing. To remove it, delete the Render services and the Neon project from
their dashboards.
