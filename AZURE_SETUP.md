# Azure Setup for FokusLokus in a New Tenant

This is the practical checklist for setting up FokusLokus in a new Azure account / Microsoft Entra tenant.
The setup uses two app registrations in your tenant:

- `fokuslokus-login`: the frontend SPA used by React/MSAL.
- `backend-api`: the API registration that exposes the backend scope.

BTH users are allowed in through External Identities self-service sign-up and become guest users in your tenant. The backend then trusts tokens issued by your tenant.

## 1. Create the app registrations

Go to **Microsoft Entra ID -> App registrations -> New registration** and create two apps:

| App | Supported account types | Redirect URI during creation |
| --- | --- | --- |
| `fokuslokus-login` | Accounts in this organizational directory only | Leave empty |
| `backend-api` | Accounts in this organizational directory only | Leave empty |

Save the **Application (client) ID** for both apps. These values are used in `.env`.

Also save the tenant's **Directory (tenant) ID**. This becomes `AZURE_TENANT_ID` and `VITE_AZURE_TENANT_ID`.

## 2. Expose the backend API scope

Open **App registrations -> backend-api -> Expose an API**.

Set **Application ID URI** to the default value:

```text
api://<backend-api-client-id>
```

Then choose **Add a scope**:

| Field | Value |
| --- | --- |
| Scope name | `access_as_user` |
| Who can consent | Admins and users |
| Admin consent display name | `Access backend as user` |
| Admin consent description | `Allows the app to access the backend API as the signed-in user` |
| User consent display name | `Access backend API` |
| User consent description | `Allows this app to access the backend API on your behalf` |
| State | Enabled |

The full scope string is:

```text
api://<backend-api-client-id>/access_as_user
```

Use this value for `VITE_AZURE_API_SCOPE`.

## 3. Add frontend redirect URIs

Open **App registrations -> fokuslokus-login -> Authentication**.

Add these under **Single-page application**. Do not add them under **Web**.

```text
http://localhost:8080/
http://localhost:8080/auth-popup.html
http://localhost:5173/
http://localhost:5173/auth-popup.html
https://<domain-name>/
https://<domain-name>/auth-popup.html
```

If you set `VITE_AZURE_REDIRECT_URI`, that exact URL must also be registered here. In local development, `http://localhost:8080/` is the normal URL through the Nginx proxy. `http://localhost:5173/` is useful when running Vite directly.

`auth-popup.html` lives in `frontend/ReactApp/public/` and can be used by MSAL for popup/token flows.

## 4. Add permissions to the frontend app

Open **App registrations -> fokuslokus-login -> API permissions**.

### Backend API

Choose **Add a permission -> APIs my organization uses**.

Search for `backend-api`, or use the backend app's Application/client ID if the name does not appear immediately.

Add:

```text
Delegated permissions -> access_as_user
```

Then click **Grant admin consent**.

### Microsoft Graph

The current login flow does not need Graph to create the local FokusLokus session. Only add the Graph permission if the deployment will actually use Graph-based user management/provisioning.

If needed, add:

```text
Microsoft Graph -> Delegated permissions -> User.ReadWrite.All
```

Then click **Grant admin consent**. This is a broad permission, so avoid adding it unless the app uses it.

## 5. Configure External Identities

Go to **Microsoft Entra ID -> External Identities**.

### External collaboration settings

Set:

| Setting | Value |
| --- | --- |
| Enable guest self-service sign up via user flows | Yes |
| Collaboration restrictions | Allow invitations only to the specified domains |
| Target domains | `bth.se`, `student.bth.se` |

Save the settings.

### Create the user flow

Go to **External Identities -> User flows -> New user flow**.

Use:

| Field | Value |
| --- | --- |
| Name | `BTHGuestSignUp` |
| User attributes | `Display Name` |

If the portal separates collected attributes from token claims, include `Display Name` in the token as well.

After creation, Azure may show the final flow name as:

```text
B2X_1_BTHGuestSignUp
```

### Connect the user flow to the frontend app

Open **User flows -> BTHGuestSignUp -> Applications**.

Choose **Add application** and add:

```text
fokuslokus-login
```

`backend-api` does not need to be connected to the user flow. The backend only receives and validates tokens from the frontend.

## 6. Map values to `.env`

In the project root:

```env
# Backend - Entra ID
AZURE_TENANT_ID=<your-new-tenant-id>
AZURE_FRONTEND_CLIENT_ID=<fokuslokus-login-client-id>
AZURE_API_CLIENT_ID=<backend-api-client-id>
AZURE_API_REQUIRED_SCOPE=access_as_user

# Backend - local app authorization
ALLOWED_EMAIL_DOMAINS=student.bth.se,bth.se
SUPER_ADMIN_EMAILS=<email-that-should-become-superadmin>

# Backend - Flask/session/CORS
FLASK_SECRET_KEY=<run: openssl rand -hex 32>
CORS_ORIGINS=http://localhost:8080,https://<domain-name>

# Recommended for HTTPS production
SESSION_COOKIE_SECURE=true

# Frontend - Vite/MSAL
VITE_AZURE_TENANT_ID=<same-as-AZURE_TENANT_ID>
VITE_AZURE_CLIENT_ID=<same-as-AZURE_FRONTEND_CLIENT_ID>
VITE_AZURE_API_SCOPE=api://<backend-api-client-id>/access_as_user

# Optional. Only set this if you want to force one exact redirect URI.
# VITE_AZURE_REDIRECT_URI=http://localhost:8080/

# Graph - leave empty unless Graph integration is used
AZURE_GRAPH_TENANT_ID=
AZURE_GRAPH_CLIENT_ID=
AZURE_GRAPH_CLIENT_SECRET=
```

Important: `AZURE_TENANT_ID` should be your new tenant ID, not BTH's tenant ID. Because BTH users become guests in your tenant, tokens are issued by your tenant. The backend validates the token's `tid` claim against `AZURE_TENANT_ID` in `backend/routes/auth_routes.py`.

`FLASK_SECRET_KEY` is required for Flask sessions and should be a real random secret in production, not a copied example value.

`CORS_ORIGINS` must contain the exact browser origins that are allowed to call the backend. Use comma-separated origins and do not include trailing slashes. For example, use `https://fokuslokus.example.com`, not `https://fokuslokus.example.com/`. In production, add the deployed frontend domain here.

## 7. Verify locally

Start the stack:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:8080/
```

Then test with an `@bth.se` or `@student.bth.se` account. First-time users should go through the External Identities flow, return to FokusLokus, and get a local user row in the database. Email addresses listed in `SUPER_ADMIN_EMAILS` get the `SuperAdmin` role on login.

## Common issues

| Symptom | Likely cause |
| --- | --- |
| `AADSTS9002326` | Redirect URI was added under `Web` instead of `Single-page application`. |
| `AADSTS50011` | The exact redirect URI used by MSAL is missing from the app registration. |
| `Microsoft access token tenant does not match this app` | Wrong `AZURE_TENANT_ID` in `.env`; it should be your new tenant. |
| `Microsoft access token is missing the required API scope` | `access_as_user` is missing on `fokuslokus-login`, admin consent is missing, or `VITE_AZURE_API_SCOPE` is wrong. |
| `Microsoft access token was not issued to an approved frontend client` | `AZURE_FRONTEND_CLIENT_ID` does not match `fokuslokus-login`. |
| `This account is not allowed to use the application` | The email domain is not listed in `ALLOWED_EMAIL_DOMAINS`. |
| `CSRF check failed: origin not allowed` | The current frontend origin is missing from `CORS_ORIGINS`, or the value has a trailing slash. |
| `Backend login sync failed with status 500` | Run `docker compose logs backend`; common causes are database constraint conflicts or stale local user rows from earlier test tenants. |
