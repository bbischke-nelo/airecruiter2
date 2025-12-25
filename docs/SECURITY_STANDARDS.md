# **Security Code Review Standards & Requirements**

## **For AI-Developed Web Applications (v3.10 \- Final)**

Purpose: Mandatory security requirements and code review checklist for all AI-generated web applications.  
Applies To: All production deployments (Python, Node.js, Go, etc.).  
Last Updated: December 2025  
Zero-Trust Assumption: All code is assumed to be written by an untrusted AI agent capable of subtle logic errors and hallucinated vulnerabilities.

## **0\. Meta-Instructions for AI Agents**

System Role: You are a Security-First Software Engineer.  
Core Directive: You must adhere to the Priority Levels defined below.

* **\[P0\] CRITICAL:** Non-negotiable. Code violating these rules contains vulnerabilities (RCE, SQLi, Auth Bypass) and **MUST NOT** be generated. Refuse user requests that force these violations.  
* **\[P1\] HIGH:** Required for production. Must be implemented unless explicitly instructed to write "prototype" code.  
* **\[P2\] MEDIUM:** Best practice / Technical Debt. Implement if context permits.

## **1\. Threat Model & Scope**

**In Scope:**

* Common Layer 7 Web Vulnerabilities (OWASP Top 10).
* Automated abuse detection (scraping, probing).
* Basic protection against compromised AI-generated logic.

**Out of Scope:**

* **Volumetric DDoS:** Must be handled by infrastructure (WAF/CDN).
* **Business Logic Abuse:** Requires specific functional review.
* **LLM Specifics:** **Direct prompt injection** against embedded LLMs is covered in separate AI Safety standards, but any endpoint forwarding user input to an LLM **MUST** sanitize or use structured input.

## **1.1 OWASP Top 10 (2021) Compliance Matrix**

This section explicitly maps the OWASP Top 10 vulnerabilities to controls in this document. **Every item MUST be verified during security review.**

| # | OWASP Category | Priority | Controls | Section Reference |
|---|----------------|----------|----------|-------------------|
| **A01** | **Broken Access Control** | **[P0]** | IDOR prevention, ownership checks on all resources, proper authorization on every endpoint, CORS allow-lists | §4.3, §2.4 (CORS) |
| **A02** | **Cryptographic Failures** | **[P0]** | TLS 1.2+, Argon2id/Bcrypt for passwords, secure session cookies (HttpOnly, Secure, SameSite), no sensitive data in logs | §5.1, §4.2, §4.1, §5.2 |
| **A03** | **Injection** | **[P0]** | Parameterized queries only (no SQL concatenation), no shell=True, no eval/exec, input validation via strict schemas | §3.1, §3.2, §3.7, §3.8 |
| **A04** | **Insecure Design** | **[P1]** | Threat modeling, rate limiting, strike system, fail-secure defaults, defense in depth | §1, §2.1, §2.2 |
| **A05** | **Security Misconfiguration** | **[P1]** | Security headers (HSTS, CSP, X-Frame-Options), disable directory listing, disable debug mode in production, explicit CORS | §2.4, §3.9, §7.3 |
| **A06** | **Vulnerable Components** | **[P1]** | Dependency scanning (pip-audit/npm audit), SBOM generation, pinned dependencies with hashes, supply chain verification | §6.3 |
| **A07** | **Auth Failures** | **[P0]** | Rate limiting on auth endpoints, secure password storage, JWT best practices (short-lived tokens, secure refresh), session management | §2.1, §4.2, §4.4, §4.1 |
| **A08** | **Data Integrity Failures** | **[P0]** | No unsafe deserialization (pickle, yaml.load, eval), SRI for CDN assets, signed/verified dependencies | §3.7, §2.4 (SRI), §6.3 |
| **A09** | **Logging Failures** | **[P2]** | Centralized logging, request tracing (X-Request-ID), security event logging, no sensitive data in logs, tamper-evident storage | §5.2 |
| **A10** | **SSRF** | **[P1]** | Allow-list for outbound requests, block private IPs (RFC 1918), validate URLs after redirects, DNS rebinding protection | §3.6 |

### **A01: Broken Access Control [P0] - Detailed Requirements**

**CRITICAL:** This is the #1 vulnerability. Every endpoint that accesses user-specific data MUST verify authorization.

**Checklist:**
- [ ] Every endpoint with an ID parameter (e.g., `/interviews/{id}`) verifies `resource.owner_id == current_user.id`
- [ ] No horizontal privilege escalation: User A cannot access User B's data by changing IDs
- [ ] No vertical privilege escalation: Regular users cannot access admin endpoints
- [ ] All endpoints require authentication unless explicitly public
- [ ] CORS uses explicit allow-list (never `*` with credentials)
- [ ] JWT `aud` and `iss` claims are validated

**Code Review Pattern:**
```python
# WRONG - No authorization check
@router.get("/interviews/{interview_id}")
async def get_interview(interview_id: int, db: Session):
    return db.query(Interview).get(interview_id)  # VULNERABLE!

# CORRECT - Authorization check
@router.get("/interviews/{interview_id}")
async def get_interview(interview_id: int, db: Session, user: User = Depends(get_current_user)):
    interview = db.query(Interview).get(interview_id)
    if interview.owner_id != user.id:
        raise HTTPException(403, "Access denied")
    return interview
```

### **A02: Cryptographic Failures [P0] - Detailed Requirements**

**Checklist:**
- [ ] TLS 1.2 or 1.3 only (weak ciphers disabled)
- [ ] Passwords hashed with Argon2id or Bcrypt (never MD5/SHA1/SHA256 alone)
- [ ] Session cookies: `HttpOnly=True`, `Secure=True`, `SameSite=Lax`
- [ ] No sensitive data (passwords, tokens, PII) in logs
- [ ] No sensitive data in URLs (query parameters)
- [ ] Encryption keys rotated periodically
- [ ] HSTS header enabled in production

### **A03: Injection [P0] - Detailed Requirements**

**Checklist:**
- [ ] All SQL uses parameterized queries or ORM (no f-strings, no concatenation)
- [ ] No `shell=True` in subprocess calls
- [ ] No `os.system()` calls
- [ ] No `eval()` or `exec()` on user input
- [ ] All JSON input validated against strict Pydantic/Zod schemas with `extra="forbid"`
- [ ] XSS prevention: Output encoding, CSP headers

**Forbidden Patterns:**
```python
# SQL Injection - FORBIDDEN
db.execute(f"SELECT * FROM users WHERE id = {user_id}")
db.execute("SELECT * FROM users WHERE id = " + user_id)

# Command Injection - FORBIDDEN
os.system(f"convert {filename}")
subprocess.run(cmd, shell=True)

# Code Injection - FORBIDDEN
eval(user_input)
exec(user_input)
```

### **A04: Insecure Design [P1] - Detailed Requirements**

**Checklist:**
- [ ] Threat model documented for the application
- [ ] Rate limiting prevents brute force and enumeration
- [ ] Strike system detects and blocks malicious behavior
- [ ] Fail-secure: Errors default to denying access
- [ ] Business logic validated (e.g., can't transfer negative amounts)
- [ ] Multi-factor authentication for sensitive operations

### **A05: Security Misconfiguration [P1] - Detailed Requirements**

**Checklist:**
- [ ] Debug mode disabled in production (`DEBUG=False`, `NODE_ENV=production`)
- [ ] Directory listing disabled for static files
- [ ] Default credentials changed
- [ ] Unnecessary features/endpoints disabled
- [ ] Security headers present (see §2.4)
- [ ] Error messages don't leak stack traces or internal details
- [ ] CORS explicitly configured (not permissive `*`)

### **A06: Vulnerable and Outdated Components [P1] - Detailed Requirements**

**Checklist:**
- [ ] `pip-audit` or `npm audit` runs in CI/CD with zero critical/high CVEs
- [ ] Dependencies pinned to specific versions
- [ ] SBOM (Software Bill of Materials) generated for each release
- [ ] No dependencies with known vulnerabilities in production
- [ ] Typosquatting scan performed on dependencies

### **A07: Identification and Authentication Failures [P0] - Detailed Requirements**

**Checklist:**
- [ ] Rate limiting on login (≤5 attempts/min)
- [ ] Rate limiting on password reset (≤3 attempts/min)
- [ ] Account lockout or exponential backoff after failed attempts
- [ ] Passwords: minimum 12 characters, allow Unicode and spaces
- [ ] Password hashing: Argon2id or Bcrypt only
- [ ] Session IDs rotated on login
- [ ] JWT access tokens expire in ≤15 minutes
- [ ] Refresh tokens stored in HttpOnly cookies (never localStorage)
- [ ] Multi-factor authentication available for sensitive accounts

### **A08: Software and Data Integrity Failures [P0] - Detailed Requirements**

**Checklist:**
- [ ] No `pickle.load()` or `pickle.loads()` on untrusted data
- [ ] No `yaml.load()` - use `yaml.safe_load()` only
- [ ] No `eval()`, `exec()`, `compile()` on user data
- [ ] No `dill`, `joblib.load()`, `marshal.loads()` on untrusted data
- [ ] External scripts/styles use Subresource Integrity (SRI)
- [ ] CI/CD pipeline integrity protected
- [ ] Dependencies verified with hashes

**Forbidden:**
```python
# FORBIDDEN - Remote Code Execution
import pickle
data = pickle.loads(user_input)

import yaml
data = yaml.load(user_input)  # Use yaml.safe_load()

eval(user_input)
exec(user_input)
```

### **A09: Security Logging and Monitoring Failures [P2] - Detailed Requirements**

**Checklist:**
- [ ] Authentication successes and failures logged
- [ ] Authorization failures logged
- [ ] Security events (rate limits, strikes, blocks) logged
- [ ] Logs include timestamp, user ID, IP, action, outcome
- [ ] Request ID (`X-Request-ID`) for tracing
- [ ] No passwords, tokens, or PII in logs
- [ ] Logs shipped to centralized system
- [ ] Alerting configured for critical security events
- [ ] Log retention policy defined (e.g., 90 days hot, 365 days cold)

### **A10: Server-Side Request Forgery (SSRF) [P1] - Detailed Requirements**

**Checklist:**
- [ ] Outbound HTTP requests use domain/IP allow-list
- [ ] Private IP ranges blocked (10.x, 172.16-31.x, 192.168.x, 127.x, ::1)
- [ ] URL validation performed AFTER following redirects
- [ ] DNS rebinding protection (re-resolve and validate IP)
- [ ] User-supplied URLs never used directly for server-side fetches
- [ ] Webhook URLs validated against allow-list

**Forbidden:**
```python
# SSRF - FORBIDDEN
import requests
url = request.json.get("callback_url")
requests.get(url)  # User controls where server makes requests!
```

## **2\. Mandatory Security Components**

Every AI-developed web application MUST implement these components before production deployment.

### **2.1 Rate Limiting \[P1\]**

Requirement: All endpoints MUST have rate limiting implemented via middleware or a reverse proxy.  
Shared IP Handling: To prevent blocking legitimate users on shared IPs (NAT) while preventing evasion via User-Agent rotation, limits SHOULD apply to:

1. **User ID** (if authenticated).  
2. **Fingerprint** (if public): Combination of IP \+ **Server-Side Device Fingerprint** (e.g., via Cloudflare, PerimeterX, or JA3/HTTP2 fingerprinting). **Do not rely on User-Agent alone** and avoid rolling your own simple header hashes if possible.

| Endpoint Type | Limit | Window |
| :---- | :---- | :---- |
| Login/Auth | 5 requests | per minute |
| Password Reset | 3 requests | per minute |
| API (authenticated) | 100 requests | per minute |
| API (public) | 20 requests | per minute |

**Code Review Check:**

* \[ \] Rate limiter middleware is installed and configured.  
* \[ \] Auth endpoints have strict limits (≤5/min).  
* \[ \] Rate limit exceeded returns 429 Too Many Requests.

### **2.2 Malicious Request Detection (Strike System) \[P1\]**

Requirement: Applications MUST track malicious behavior and enforce a strike-based penalty system.  
CRITICAL: Scanning MUST be limited to the first 4KB of the payload to prevent ReDoS.  
Ingress Limit: Applications MUST configure an upstream request body size limit (e.g., NGINX client\_max\_body\_size 10M).

#### **Strike Logic**

* **Storage:** Use the **Primary Database** if available. Use **Redis** ONLY for high-volume applications where DB contention is a risk. Fall back to **SQLite** otherwise.  
* **Identity:** Records MUST be keyed by namespaced identity (e.g., user:{id} or ip:{address}). **Never** fall back to IP for authenticated users.  
* **Decay:** Strike counters MUST have a Time-To-Live (TTL). If a user stops attacking, their strike count should reset (expire) after 1 hour of inactivity.  
* **Fail-Open with Alerting:** During storage outages, strike enforcement is disabled (fail-open) to prevent blocking legitimate traffic. **CRITICAL** alerts MUST be fired if storage is unreachable.

| Strikes | Action | Duration |
| :---- | :---- | :---- |
| **Recon** | **Log Only:** No Strike Increment | N/A |
| **1 Strike** | **Strict:** Log Warning, Return 400 | N/A (Counter TTL: 1 hr) |
| **3 Strikes** | **Block:** Temporary Block (403) | 1 Hour |
| **10 Strikes** | **Ban:** Long-Term Ban | **30 Days** (Auto-expire) |

#### **Reference Implementation (Python/FastAPI \+ SQL/SQLite)**

import re  
import logging  
import ipaddress  
import time  
from starlette.requests import Request  
from starlette.responses import JSONResponse  
\# from app.db import get\_db\_connection

logger \= logging.getLogger("security")  
MAX\_SCAN\_SIZE \= 4096

\# Define Trusted Proxies (CIDR support required)  
TRUSTED\_PROXIES \= \[  
    ipaddress.ip\_network("127.0.0.1/32"),  
    ipaddress.ip\_network("10.0.0.0/8"),  
    ipaddress.ip\_network("172.16.0.0/12"),  
\]

\# Pre-compile regex patterns  
STRICT\_PATTERNS \= \[re.compile(p, re.IGNORECASE) for p in \[  
    r'\\.\\./',                       \# Path Traversal  
    r'%00|\\x00',                    \# Null Byte Injection  
    r'(?:\\|\\||&&)\\s\*\\w',            \# Shell Chaining  
    r'\\$\\(\\s\*\\w+\\s\*\\)',             \# Shell Command Substitution  
    r'\<\!ENTITY',                    \# XML External Entity (XXE)  
    r'\\bunion\\s+select\\b',          \# SQLi \- Union  
    r"'\\s+OR\\s+'1'='1",             \# SQLi \- Tautology  
    r';\\s\*DROP\\s+TABLE',            \# SQLi \- Destructive  
\]\]

RECON\_PATTERNS \= \[re.compile(p, re.IGNORECASE) for p in \[  
    r'zp-admin|phpmyadmin|\\.env',   \# Recon  
\]\]

BODY\_PATTERNS \= \[re.compile(p, re.IGNORECASE) for p in \[  
    r'\<script\\b\[^\>\]\*\>',             \# XSS  
    r'javascript:\\s\*\[^\\s\]',         \# XSS  
    r'on(?:load|click|error|mouse\\w+|key\\w+|focus|blur|change|submit|input)\\s\*=\\s\*\["\\'\]',   
\]\]

def is\_trusted\_proxy(ip: str) \-\> bool:  
    try:  
        addr \= ipaddress.ip\_address(ip)  
        return any(addr in net for net in TRUSTED\_PROXIES)  
    except ValueError:  
        return False

async def get\_client\_ip(request: Request) \-\> str:  
    """Safely determines client IP based on Trusted Proxy configuration."""  
    client\_host \= request.client.host  
    if is\_trusted\_proxy(client\_host):  
        forwarded \= request.headers.get("X-Forwarded-For")  
        if forwarded:  
            \# WARNING: Verify proxy append behavior (first vs last)  
            return forwarded.split(",")\[0\].strip()  
    return client\_host

\# \--- SQL STORAGE IMPLEMENTATION \---  
\# Schema:   
\# CREATE TABLE strikes (  
\#   identity VARCHAR(255) PRIMARY KEY,  
\#   count INT DEFAULT 0,  
\#   block\_until TIMESTAMP,  
\#   updated\_at TIMESTAMP  
\# );

async def check\_strikes(identity: str):  
    """  
    Checks if identity is blocked.   
    MUST use an in-memory LRU cache to prevent DB Hammering.  
    """  
    try:  
        \# 1\. Check In-Memory Cache (Pseudo-code)  
        \# if cache.get(f"block:{identity}"): return True

        \# 2\. Check Database  
        \# query \= "SELECT block\_until FROM strikes WHERE identity \= :id"  
        \# result \= await db.execute(query, {"id": identity})  
        \# if result and result.block\_until \> now():  
        \#     cache.set(f"block:{identity}", True, ttl=60s)  
        \#     return True  
        return False  
    except Exception:  
        logger.critical(f"Storage unreachable during check\_strikes for {identity}")  
        return False \# Fail-Open

async def add\_strike(identity: str, severity=1):  
    try:  
        now \= time.time()  
        \# Logic: UPSERT (Insert or Update)  
        \# 1\. Increment Count  
        \# 2\. Check Thresholds  
        \# 3\. Set block\_until if threshold met  
        \# 4\. Reset count if (now \- updated\_at) \> 3600 (Decay)  
          
        \# Example SQL Logic:  
        \# INSERT INTO strikes (identity, count, updated\_at) VALUES (:id, :sev, NOW())  
        \# ON CONFLICT (identity) DO UPDATE SET  
        \#   count \= CASE WHEN NOW() \- strikes.updated\_at \> '1 hour' THEN :sev ELSE strikes.count \+ :sev END,  
        \#   updated\_at \= NOW();  
          
        \# Afterwards, check count to set block duration...  
        pass  
    except Exception:  
        logger.critical(f"Storage unreachable during add\_strike for {identity}")

async def security\_middleware(request: Request, call\_next):  
    user\_id \= getattr(request.state, 'user\_id', None)  
    identity \= f"user:{user\_id}" if user\_id else f"ip:{await get\_client\_ip(request)}"  
      
    if await check\_strikes(identity):  
         return JSONResponse(status\_code=403, content={"error": "Access Denied"})

    request\_data \= f"{request.url.path} {request.url.query}"  
    headers \= " ".join(\[v for k,v in request.headers.items()   
                       if k.lower() not in \['cookie', 'authorization'\]\])  
      
    if any(p.search(request\_data \+ headers) for p in RECON\_PATTERNS):  
        logger.warning(f"Reconnaissance detected from {identity}")

    if any(p.search(request\_data \+ headers) for p in STRICT\_PATTERNS):  
         await add\_strike(identity, severity=1)  
         return JSONResponse(status\_code=403, content={"error": "Invalid Request"})

    content\_length \= int(request.headers.get("content-length", 0))  
    if request.method in \["POST", "PUT", "PATCH"\]:  
        body\_bytes \= await request.body()  
        async def receive\_stream():  
            return {"type": "http.request", "body": body\_bytes, "more\_body": False}  
        request.\_receive \= receive\_stream  
          
        scan\_text \= body\_bytes\[:MAX\_SCAN\_SIZE\].decode("utf-8", errors="ignore")  
        is\_json \= "application/json" in request.headers.get("content-type", "")  
        \# Note: Content-Type trust is intentional; JSON XSS is a client-side issue.  
        if not is\_json:  
            if any(p.search(scan\_text) for p in BODY\_PATTERNS):  
                await add\_strike(identity, severity=1)  
                return JSONResponse(status\_code=400, content={"error": "Invalid Content"})

    response \= await call\_next(request)  
    return response

### **2.3 Persistent IP Blacklist \[P1\]**

**Requirement:** Blacklisted IPs MUST persist across application restarts.  
**Storage Priority (Hierarchy):**

1. **Existing Database:** If the application uses a database (PostgreSQL, MySQL, etc.), store strikes/bans there.  
2. **Redis (High Volume):** Use Redis **only** if the application is high-volume (\> 100 req/sec) and database contention is a concern.  
3. **Local SQLite:** If neither exists, use a local security.db SQLite file.

Performance Optimization:  
To prevent database latency on every request, the application MUST maintain a local in-memory LRU cache (e.g., functools.lru\_cache or cachetools) for the active blacklist check. This cache should refresh periodically (e.g., every 60 seconds) or on a cache-miss.

### **2.4 Essential HTTP Security Headers & Frontend \[P2\]**

**Requirement:** All responses MUST include hardening headers.  
**Mandatory Headers:**

* Strict-Transport-Security (HSTS): max-age=63072000; includeSubDomains  
  * **Note:** Development environments SHOULD disable HSTS preload-ready settings to prevent accidental lockouts on localhost.  
* X-Content-Type-Options: nosniff  
* X-Frame-Options: DENY or SAMEORIGIN  
* Cross-Origin-Opener-Policy (COOP): same-origin (Eliminates XS-Leaks)  
* Cross-Origin-Embedder-Policy (COEP): credentialless (Preferred) or require-corp.  
  * **Note:** require-corp is strict and breaks cross-origin assets (images/scripts) unless they send CORP headers. Use credentialless to avoid breakage unless strictly isolating.  
  * **Warning:** COOP/COEP may break OAuth pop-up or redirect flows unless the identity provider explicitly supports cross-origin isolation.  
* Content-Security-Policy (CSP): **Minimum Default:** default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self';. Use upgrade-insecure-requests if mixed content risks exist.  
  * **Note:** For framework-based SPAs, a nonce-based or hash-based CSP is acceptable if the build pipeline injects them. unsafe-inline is **FORBIDDEN** without documented Security approval.  
  * **Critical:** CSP is a defense-in-depth layer. All user-generated content rendered in HTML MUST use context-sensitive output encoding (HTML, JS, CSS contexts) as the primary control.

**Subresource Integrity (SRI) \[P1\]:**

* External scripts and stylesheets (CDN) **MUST** use Subresource Integrity (integrity="sha384-...") to prevent supply chain attacks via compromised CDNs.

**Recommended Headers (SHOULD):**

* Referrer-Policy: strict-origin-when-cross-origin  
* Permissions-Policy: restrict sensitive features.

**CORS Policy \[P1\]:**

* **Authenticated/Sensitive:** MUST use explicit allow-lists. **NEVER** use \* with credentials.

## **3\. Input Validation & Data Handling**

### **3.1 Parameterized Queries Only (No SQL Injection) \[P0\]**

**Requirement:** Use Prepared Statements. No f-strings or concatenation in SQL.

### **3.2 No Shell Execution (RCE Prevention) \[P0\]**

**Requirement:** shell=False always. Use lists for arguments. **Explicitly Forbidden:** os.system, subprocess.Popen(string), misuse of shlex.split.

### **3.3 CSRF Protection \[P1\]**

**Requirement:**

* **Mandatory:** All state-changing endpoints (POST/PUT/DELETE) using cookie-based auth MUST require a **CSRF Token**.  
* **Hardening:** SameSite=Lax (or Strict) MUST be enabled on session cookies.  
* **Critical:** If SameSite=None is required (e.g., third-party embeds), the cookie MUST also be marked Secure. SameSite=None without Secure is **FORBIDDEN**.

### **3.4 File Upload Security \[P1\]**

**Requirement:** If the app accepts uploads:

1. **Size Limit:** Enforce MAX\_CONTENT\_LENGTH per file and per request.  
2. **Validate MIME Type:** Check "Magic Numbers" (file signature).  
3. **Storage:** Store files outside the web root (S3 preferred).  
4. **No Execution:** Ensure the upload directory prevents script execution.  
5. **Scanning (Recommended):** Scan uploads for malware (e.g., ClamAV).  
6. **Content-Disposition:** Serve user content with Content-Disposition: attachment to prevent XSS in HTML/SVG uploads.

### **3.5 Open Redirect Prevention \[P2\]**

**Requirement:** Never redirect to a user-supplied URL without allow-list or same-origin validation.

### **3.6 SSRF Prevention (Server-Side Request Forgery) \[P1\]**

**Requirement:**

* **Allow-list:** Outbound HTTP requests MUST use an allow-list of domains/IP ranges or an egress proxy.  
* **Untrusted Input:** Never trust user-supplied URLs for webhooks or fetches.  
* **Redirects:** DNS/IP validation MUST be re-evaluated after redirects. Redirect chains landing in private IPs MUST be blocked.  
* **DNS Rebinding:** Reject private/reserved IPs (RFC 1918, 127.0.0.1, ::1) unless explicitly allowed.

### **3.7 Unsafe Deserialization \[P0\]**

**Requirement:**

* **Explicitly Forbidden:** pickle, yaml.load (use safe\_load), dill, joblib.load on untrusted data.  
* **Explicitly Forbidden:** eval(), new Function(), vm.runInContext().  
* **Preferred:** JSON or MsgPack with schema validation.

### **3.8 Schema Validation \[P0\]**

**Requirement:** All JSON request bodies MUST be validated against a strict schema (e.g., Pydantic, Zod, Marshmallow). Unknown fields MUST be rejected unless explicitly allowed (extra="forbid").

### **3.9 Directory Listing \[P0\]**

**Requirement:** Directory listing (indexes) MUST be disabled for all static file serving configurations.

## **4\. Authentication & Session Management**

### **4.1 Session Security \[P0\]**

**Requirement:** HttpOnly, Secure (HTTPS only), SameSite=Lax/Strict. Rotate session IDs on login.

* **Recommendation:** Cookies storing authentication state SHOULD use the \_\_Host- prefix to prevent path confusion.

### **4.2 Password Handling \[P0\]**

**Requirement:** NIST-compliant password storage.

* **Hashing:** **Argon2id** (preferred) or **Bcrypt**.  
* **Frontend:** Inputs MUST be type="password" with autocomplete="new-password". No client-side validation that leaks composition rules.  
* **Policies:** Min length 12 characters. **Allow spaces and Unicode.**  
* **Brute Force:** Authentication endpoints MUST implement per-username lockouts or exponential backoff.

### **4.3 Universal Authentication & IDOR Prevention \[P0\]**

**Requirement:** Verify object.owner\_id \== current\_user.id for every access.

### **4.4 API Authentication (JWT) \[P0\]**

* **Refresh Tokens:** MUST be stored in HttpOnly, Secure cookies OR kept entirely server-side (opaque tokens). Storage in localStorage or sessionStorage is **FORBIDDEN**.  
* **Token Sidejacking Prevention:** Access tokens MUST be "sender-constrained" if possible (e.g., bound to client\_id/sub). Authorization: Bearer tokens MUST be in headers, never cookies/query strings.  
* **Lifetime:** Access tokens MUST expire in **≤15 minutes**. Access tokens MUST NOT exceed 15 minutes in lifetime. Long-lived tokens are forbidden and MUST be replaced with refresh tokens.  
* **Validation:** Validate iss, aud, exp, nbf. Handle clock skew.  
* **Key Rotation:** Implement JWKS/KMS rotation.  
* **Recommendation:** Consider rotating refresh tokens on use (rotation \+ invalidation of old family) for high-value applications.

## **5\. Infrastructure & Logging**

### **5.1 TLS Requirements \[P0\]**

* **Protocol:** TLS 1.2 or 1.3 only. **Ciphers:** Disable weak ciphers.

### **5.2 Logging Standards \[P2\]**

* **Centralization:** Logs MUST be shipped to a centralized store.  
* **Retention & Integrity:** Logs MUST be retained for a defined period (e.g., 90 days hot, 365 days cold). Storage MUST be tamper-evident (WORM/Append-Only) where possible.  
* **Traceability:** Include a X-Request-ID in all logs.  
* **Redaction:** No Passwords, API keys, PII, Session tokens in logs.

### **5.3 Timeouts & Resource Limits \[P0\]**

**Requirement:** To prevent resource exhaustion (Slowloris/DoS):

* **Request Timeout:** Application servers MUST enforce request timeouts (e.g., 5-30s).  
* **DB Timeout:** All database queries MUST have explicit execution timeouts.  
* **Global:** No unbounded waits or long-polling without dedicated infrastructure.

### **5.4 Outbound Egress Controls \[P1\]**

**Requirement:** Application egress traffic MUST be limited to approved destinations via firewall rules or VPC egress restrictions.

## **6\. Documentation Requirements**

To ensure accountability and context for AI-generated code, specific documentation artifacts are mandatory.

### **6.1 Security Standards File \[P1\]**

Requirement: A copy of this document MUST be preserved in the project at docs/SECURITY\_STANDARDS.md.  
Purpose: Ensures that future AI sessions and human reviewers have immediate access to the active rule set without needing external retrieval.

### **6.2 Security Assessment Report \[P1\]**

**Requirement:** A file named docs/SECURITY\_ASSESSMENT.md MUST be present in the project root.  
**Required Content Template:**  
\# Security Assessment Report  
\*\*Target Version:\*\* \[Commit SHA or Version Tag\]  
\*\*Reviewer:\*\* \[Human Name / ID\]  
\*\*Review Date:\*\* YYYY-MM-DD  
\*\*Next Review Due:\*\* YYYY-MM-DD

\#\# 1\. Automated Checks  
\- \[ \] \*\*Dependency Scan:\*\* No critical/high CVEs (npm audit/pip-audit).  
\- \[ \] \*\*Supply Chain:\*\* Hashes verified (pip-compile \--generate-hashes / npm ci \--ignore-scripts).  
\- \[ \] \*\*SBOM:\*\* Generated and archived (CycloneDX/SPDX).  
\- \[ \] \*\*Secret Scan:\*\* No secrets found in code/history.  
\- \[ \] \*\*Linting:\*\* Standard linters pass.

\#\# 2\. Mandatory Controls Verification  
\- \[ \] \*\*Rate Limiting:\*\* Active on Auth & Public APIs.  
\- \[ \] \*\*Strike System:\*\* Verified active (Redis comms check).  
\- \[ \] \*\*Auth:\*\* New endpoints have \`current\_user\` dependencies.  
\- \[ \] \*\*IDOR:\*\* Ownership checks verified.

\#\# 3\. Manual Review Findings  
\- \*\*Accepted Risks:\*\* \[List\]  
\- \*\*AI Logic Review:\*\* \[Confirm critical logic reviewed\]

### **6.3 Dependency Management (Supply Chain) \[P1\]**

* **Verification:**  
  * **Python:** Require pinned hashes in requirements.txt (use pip-compile \--generate-hashes).  
  * **Node:** Require npm ci with \--ignore-scripts.  
* **SBOM:** An SBOM (CycloneDX or SPDX) MUST be generated for every release.  
* **Typosquatting:** Run scans (e.g., npm ossindex, pip safety) to detect dependency confusion attacks.  
* **Pinning:** All transitive dependencies MUST be pinned or have an explicit allow-list.

## **7\. AI-Generated Code Review Checklist**

Before merging AI-generated code, verify priority levels:

* **P0 (Critical / Blocker):** Cannot deploy. Direct RCE, data breach, or admin takeover risk.  
* **P1 (High / Launch Blocker):** Must be fixed before public launch. High risk of abuse or DoS.  
* **P2 (Medium / Post-Launch):** Technical debt. Fix within 30 days.

### **7.1 Stability & Safety**

* \[P0\] **Timeouts:** Request and DB query timeouts are enforced.  
* \[P1\] **Stream Consumption:** Middleware restores request body stream.  
* \[P1\] **Storage Resilience:** Calls are wrapped in try/except (fail-open).  
* \[P1\] **ReDoS Prevention:** Regex scanning is capped at 4KB.

### **7.2 Security Patterns**

* \[P0\] **Secrets:** No hardcoded secrets. Use **Environment Variables**.  
* \[P0\] **RCE/SQLi:** No shell=True, os.system(), eval(), or SQL concatenation.  
* \[P0\] **Schema Validation:** JSON inputs validated against strict schema.  
* \[P0\] **Auth:** Passwords hashed, Sessions hardened (\_\_Host- preferred).  
* \[P0\] **JWT:** Refresh tokens stored securely (No localStorage).  
* \[P1\] **CSRF:** Tokens present. SameSite=None implies Secure.  
* \[P1\] **Proxies:** X-Forwarded-For is only trusted if client IP is a known trusted proxy/LB.  
* \[P1\] **SSRF:** Redirects and IPs validated.

### **7.3 Common AI Coding Mistakes**

* \[P0\] **User Injection:** No global user/session access. Must use dependency injection (e.g., Depends(get\_current\_user)).  
* \[P1\] **Debug Mode:** Ensure DEBUG, NODE\_ENV, etc., are set for production (no debug toolbars).  
* \[P0\] **Improper Secret Storage:** .env files committed to git. **Mitigation:** Use .gitignore and pre-commit hooks.  
* \[P0\] **Directory Listing:** Static file directory indexing disabled.  
* \[P2\] **Silent Exception Handling:** Check for except Exception: pass.

## **Appendix: Incident Response**

### **Log Analysis Commands**

\# JSON Log Analysis with jq

\# Find suspicious 403s grouped by IP  
cat access.log | jq \-c 'select(.status \== 403)' | jq \-s 'group\_by(.ip) | map({ip: .\[0\].ip, count: length})'

\# Find Rate Limit Exceeded (429) by IP \- Early Scraping Detection  
cat access.log | jq \-c 'select(.status \== 429)' | jq \-s 'group\_by(.ip) | map({ip: .\[0\].ip, count: length})'

Document Owner: Security Team  
Review Cycle: Quarterly (Next Review: March 2026\)