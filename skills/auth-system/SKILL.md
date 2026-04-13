---
name: auth-system
description: Implement secure authentication and authorization systems with JWT, OAuth2, Session-based auth, and RBAC. Use when: (1) implementing user login/signup, (2) setting up JWT tokens, (3) OAuth2 integration (Google, GitHub, etc.), (4) role-based access control (RBAC), (5) password hashing and validation, (6) session management, (7) API authentication middleware, (8) 2FA/MFA setup. Triggers: "authentication", "login", "JWT", "OAuth", "session", "password hash", "RBAC", "permissions", "2FA".
---

# Authentication System

Production-grade authentication and authorization implementation.

## Authentication Strategies

### 1. JWT (Stateless)

```javascript
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');

// Signup
async function signup(email, password) {
  const hashedPassword = await bcrypt.hash(password, 12);
  const user = await User.create({ email, password: hashedPassword });
  return generateTokens(user);
}

// Login
async function login(email, password) {
  const user = await User.findByEmail(email);
  if (!user || !await bcrypt.compare(password, user.password)) {
    throw new Error('Invalid credentials');
  }
  return generateTokens(user);
}

// Token generation
function generateTokens(user) {
  const accessToken = jwt.sign(
    { userId: user.id, role: user.role },
    process.env.JWT_SECRET,
    { expiresIn: '15m' }
  );
  
  const refreshToken = jwt.sign(
    { userId: user.id, tokenVersion: user.tokenVersion },
    process.env.REFRESH_SECRET,
    { expiresIn: '7d' }
  );
  
  return { accessToken, refreshToken };
}

// Middleware
function authMiddleware(req, res, next) {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) return res.status(401).json({ error: 'Unauthorized' });
  
  try {
    req.user = jwt.verify(token, process.env.JWT_SECRET);
    next();
  } catch (err) {
    res.status(401).json({ error: 'Invalid token' });
  }
}
```

### 2. Session-Based (Stateful)

```javascript
const session = require('express-session');
const RedisStore = require('connect-redis')(session);

app.use(session({
  store: new RedisStore({ client: redisClient }),
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: true, // HTTPS only
    httpOnly: true, // No JS access
    maxAge: 24 * 60 * 60 * 1000, // 24 hours
    sameSite: 'strict'
  }
}));

// Login
app.post('/login', async (req, res) => {
  const user = await validateCredentials(req.body);
  req.session.userId = user.id;
  req.session.role = user.role;
  res.json({ success: true });
});

// Logout
app.post('/logout', (req, res) => {
  req.session.destroy();
  res.json({ success: true });
});
```

### 3. OAuth2 (Social Login)

```javascript
const passport = require('passport');
const GoogleStrategy = require('passport-google-oauth20').Strategy;

passport.use(new GoogleStrategy({
  clientID: process.env.GOOGLE_CLIENT_ID,
  clientSecret: process.env.GOOGLE_CLIENT_SECRET,
  callbackURL: '/auth/google/callback'
}, async (accessToken, refreshToken, profile, done) => {
  let user = await User.findByGoogleId(profile.id);
  if (!user) {
    user = await User.createFromGoogle(profile);
  }
  done(null, user);
}));

// Routes
app.get('/auth/google', passport.authenticate('google', { scope: ['email', 'profile'] }));
app.get('/auth/google/callback', 
  passport.authenticate('google', { session: false }),
  (req, res) => {
    const tokens = generateTokens(req.user);
    res.redirect(`/callback?token=${tokens.accessToken}`);
  }
);
```

## Authorization (RBAC)

```javascript
// Role definitions
const ROLES = {
  ADMIN: 'admin',
  USER: 'user',
  MODERATOR: 'moderator'
};

// Permission definitions
const PERMISSIONS = {
  [ROLES.ADMIN]: ['read', 'write', 'delete', 'manage_users'],
  [ROLES.MODERATOR]: ['read', 'write', 'delete'],
  [ROLES.USER]: ['read', 'write']
};

// Middleware
function requirePermission(permission) {
  return (req, res, next) => {
    const userPermissions = PERMISSIONS[req.user.role] || [];
    if (!userPermissions.includes(permission)) {
      return res.status(403).json({ error: 'Forbidden' });
    }
    next();
  };
}

// Usage
app.delete('/posts/:id', 
  authMiddleware, 
  requirePermission('delete'), 
  deletePost
);
```

## Password Security

```javascript
const bcrypt = require('bcrypt');
const crypto = require('crypto');

// Hash password
async function hashPassword(password) {
  const salt = await bcrypt.genSalt(12);
  return bcrypt.hash(password, salt);
}

// Validate password
async function validatePassword(password, hash) {
  return bcrypt.compare(password, hash);
}

// Generate secure token (for password reset)
function generateResetToken() {
  return crypto.randomBytes(32).toString('hex');
}
```

## 2FA (TOTP)

```javascript
const speakeasy = require('speakeasy');
const QRCode = require('qrcode');

// Setup 2FA
async function setup2FA(userId) {
  const secret = speakeasy.generateSecret({
    name: 'MyApp',
    length: 20
  });
  
  await User.update(userId, { 
    twoFactorSecret: secret.base32,
    twoFactorEnabled: false 
  });
  
  const qrUrl = await QRCode.toDataURL(secret.otpauth_url);
  return { secret: secret.base32, qrUrl };
}

// Verify 2FA
function verify2FA(secret, token) {
  return speakeasy.totp.verify({
    secret,
    encoding: 'base32',
    token,
    window: 1 // Allow 1 step before/after
  });
}
```

## Security Best Practices

```
✅ Always use HTTPS in production
✅ Store passwords with bcrypt (cost factor >= 12)
✅ Use short-lived access tokens (15-30 min)
✅ Implement refresh token rotation
✅ Set secure cookie flags (httpOnly, secure, sameSite)
✅ Rate limit login attempts
✅ Log failed authentication attempts
✅ Implement account lockout after N failures
✅ Never store tokens in localStorage (XSS risk)
✅ Use CSRF protection for session-based auth
```

## Scripts

- `scripts/generate_jwt_secret.js` - Generate secure JWT secret
- `scripts/hash_password.js` - CLI tool to hash passwords
- `scripts/verify_token.js` - Decode and verify JWT tokens

## References

- `references/oauth_providers.md` - OAuth2 provider setup guides
- `references/security_checklist.md` - Auth security audit checklist
- `references/token_refresh_flow.md` - Refresh token rotation patterns
