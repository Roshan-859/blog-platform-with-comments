# The Daily Draft

A warm, responsive community blogging app with accounts, publishing, editing, deleting, and comments.

## Run it

Requires Python 3.10 or newer. No third-party packages are needed.

```sh
python3 server.py
```

Open [http://localhost:8000](http://localhost:8000). The SQLite database (`blog.db`) is created automatically next to the server on first launch. Stop the server with Ctrl+C.

Set `PORT` to change the local port. Set `BLOG_SECRET` to a long random value before hosting the app so session tokens use a private key. Use HTTPS and a production-grade server configuration before making a public deployment.

## What’s included

- User registration, login, logout, hashed passwords, and signed HTTP-only sessions
- REST API for posts, comments, the signed-in user, and post editing/deletion
- SQLite storage with foreign-key cleanup for comments when a post is removed
- Responsive story feed, post detail view, comment conversation, and writing forms

## API overview

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/api/register` | Create an account |
| `POST` | `/api/login` | Sign in |
| `POST` | `/api/logout` | Sign out |
| `GET` | `/api/me` | Get the current user |
| `GET`, `POST` | `/api/posts` | List or publish posts |
| `PATCH`, `DELETE` | `/api/posts/{id}` | Edit or delete your post |
| `GET`, `POST` | `/api/posts/{id}/comments` | List or add comments |

This starter app is designed to run locally for learning and development.
