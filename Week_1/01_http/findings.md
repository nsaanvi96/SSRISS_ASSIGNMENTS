# Assignment 1 — Findings

## 1. What is the difference between the requested URL and final URL?

The requested URL is whatever I typed in and passed to the script. The final URL is
where the response actually ended up after any redirects were followed. Most of the
time they're the same, but with something like `http://github.com`, the requested
URL stays `http://github.com` while the final URL becomes `https://github.com/` —
the server bounced me from http to https before actually serving the page.

## 2. How can your program determine whether the server returned HTML?

By checking the `Content-Type` response header and seeing if it contains
`text/html`. I can't just guess based on the URL or assume it's HTML by default —
`httpbin.org/json` and `google.com/robots.txt` both returned 200 with a normal body,
but their `Content-Type` was `application/json` and `text/plain` respectively, so my
`is_html_response` check correctly flagged both as `False`.

## 3. What should a crawler do after receiving 429?

Back off instead of hammering the endpoint again immediately. If the server sends a
`Retry-After` header, respect it. If not, wait some reasonable amount of time before
trying again, and don't just loop-retry — a 429 is the server telling you to slow
down, not a random glitch to push through.

## 4. What should your crawler do after receiving 403?

Stop. A 403 means access is being denied on purpose, and per the working rules for
this project, that's an access boundary — not something to work around. No retries,
no header/UA spoofing, no trying alternate paths to get the same content.

## 5. Why should every HTTP request have a timeout?

Without one, a single unresponsive server can hang the request indefinitely and
freeze the whole crawler. I actually don't want one dead or slow site to block
progress on everything else I'm supposed to be checking.

## 6. Why is repeatedly retrying a failing endpoint dangerous?

It can look like abusive traffic to the server (and get me rate-limited or blocked
outright), and it puts unnecessary load on a site that might already be struggling.
It also just doesn't help — if something is failing for a structural reason (like a
403 or a dead endpoint), retrying blindly won't fix that.
