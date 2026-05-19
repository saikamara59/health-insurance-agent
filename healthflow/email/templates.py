def render_password_reset(email: str, reset_url: str) -> tuple[str, str, str]:
    """Return (subject, text_body, html_body) for a password-reset email."""
    subject = "Reset your HealthFlow password"
    text_body = f"""Hello,

We received a request to reset your HealthFlow password.

Click this link within the next hour to set a new password:
{reset_url}

If you didn't request this, you can safely ignore this email.

— HealthFlow
"""
    html_body = f"""<p>Hello,</p>
<p>We received a request to reset your HealthFlow password.</p>
<p><a href="{reset_url}">Reset password</a> (link expires in 1 hour)</p>
<p>If you didn't request this, you can safely ignore this email.</p>
<p>— HealthFlow</p>
"""
    return subject, text_body, html_body
