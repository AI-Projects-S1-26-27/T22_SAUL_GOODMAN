# Hosting the live server (prepared, not deployed)

Today the hosted site is **static**: Vercel serves `courtroom/viz/web` (see `vercel.json`), so it plays the 160 recorded trials and shows the
stored lab results, and says live features need the server. The rubric says hosting the demo live online is "highly recommended". This page
is how to host the **live** server, so that the examiner can run fresh trials, edit a case and use the analysis endpoints from a URL. The
team decides whether to do it; nothing here has been deployed or pushed.

## What gets hosted

`python -m courtroom serve --host 0.0.0.0 --port $PORT` starts FastAPI, which serves the web app and `/api/*`. It needs no database and no
model key. The language-model layer is off by default and every route that would call a model answers 503 when no key is set, so **do not set
a model key on a public host**.

## Files prepared

- `Dockerfile` and `.dockerignore` at the repository root (an editable install, so the voices and fonts are served).
- The server refuses any Host header that is not local. A deployment names its own host(s) in `COURTROOM_ALLOWED_HOSTS` (comma separated, no
  wildcard; `*` is ignored on purpose). Test: `tests/test_api_hardening.py::test_a_deployment_can_name_its_own_host_but_a_wildcard_is_ignored`.

## One free host, step by step (Render, free web service)

1. Push the repository to a GitHub account the team controls (see `docs/process/PUSH_PLAN.md`).
2. On render.com: New, Web Service, connect the repository, Runtime **Docker**, instance type **Free**.
3. Environment variables: `COURTROOM_ALLOWED_HOSTS` = the service's host name, for example `saul-goodman-courtroom.onrender.com` (it is shown
   after the first deploy; set it, then redeploy). Do not add any API key.
4. Deploy, then open `https://<host>/` and check the badge in the courtroom says **LIVE**, and `https://<host>/api/health` answers.
5. Keep the static site as the fallback; the free tier sleeps after inactivity, so open the page a few minutes before the demo.

Other hosts work the same way: any container host that passes the port in `$PORT` (Fly.io, Hugging Face Spaces with the Docker SDK, Google Cloud
Run). Set `COURTROOM_ALLOWED_HOSTS` to the public host name each time.

## Limits to know before the demo

- Heavy endpoints are capped at two at a time and the rest get a 503, but there is **no per-request time limit** (`docs/CODE_REVIEW.md`, API1).
  On a small free instance a few simultaneous analysis requests will be slow; ordinary trials take milliseconds.
- A free instance sleeps when idle and starts in a minute or so.
- The hosted copy has no analyst chat model; the page's built-in analyst answers from the stored numbers.
- Do the rehearsal in `docs/REHEARSAL.md` against the hosted URL too, and keep the local server as the primary plan.

## What was and was not tested

The server was started with `COURTROOM_ALLOWED_HOSTS` set and answered for that host and refused another (below). Docker is not installed on the machine this was prepared on, so **the image itself has not been built**; build it once before relying on it.

## Check without Docker

```bash
pip install -e .
COURTROOM_ALLOWED_HOSTS=demo.example.org python -m courtroom serve --port 8000 &
curl -s -H "Host: demo.example.org" http://127.0.0.1:8000/api/health
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: evil.example" http://127.0.0.1:8000/api/health   # 400
```
