import nodemailer from "nodemailer";

function requireEmailEnv(key: string): string {
  const value = process.env[key];

  if (!value) {
    console.error(`[Email] Missing required env var: ${key}`);
  }

  return value || "";
}

const transporter = nodemailer.createTransport({
  host: requireEmailEnv("SMTP_HOST"),
  port: Number.parseInt(process.env.SMTP_PORT || "587", 10),
  secure: process.env.SMTP_SECURE === "true",
  auth: {
    user: requireEmailEnv("SMTP_USER"),
    pass: requireEmailEnv("SMTP_PASS"),
  },
});

void transporter.verify().then(
  () => {
    console.log("[Email] SMTP connection verified - ready to send");
  },
  (error: unknown) => {
    const message = error instanceof Error ? error.message : "Unknown SMTP error";
    console.error("[Email] SMTP connection failed:", message);
    console.error("[Email] Check SMTP_* vars in .env");
  }
);

export async function sendEmail({
  to,
  subject,
  html,
}: {
  to: string;
  subject: string;
  html: string;
}) {
  try {
    const info = await transporter.sendMail({
      from: process.env.EMAIL_FROM,
      replyTo: process.env.EMAIL_REPLY_TO,
      to,
      subject,
      html,
    });

    console.log("[Email] Sent:", info.messageId);
    return { success: true, messageId: info.messageId };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown send error";
    console.error("[Email] Send failed:", message);
    return { success: false, error: message };
  }
}

export function meetingConfirmationTemplate({
  userName,
  userEmail,
  purpose,
  preferredTime,
  meetLink,
}: {
  userName: string;
  userEmail: string;
  purpose: string;
  preferredTime: string;
  meetLink?: string;
}): string {
  return `
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;color:#1f1f1f">
      <div style="background:#7c3aed;padding:24px;border-radius:8px 8px 0 0">
        <h2 style="color:white;margin:0">Meeting Confirmed - Ilmora Studios</h2>
      </div>
      <div style="padding:24px;border:1px solid #e5e7eb;border-radius:0 0 8px 8px">
        <p>Hi ${userName},</p>
        <p>Your meeting with the Ilmora Studios team is confirmed.</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="border-bottom:1px solid #e5e7eb">
            <td style="padding:8px;font-weight:600;width:140px">Name</td>
            <td style="padding:8px">${userName}</td>
          </tr>
          <tr style="border-bottom:1px solid #e5e7eb">
            <td style="padding:8px;font-weight:600">Email</td>
            <td style="padding:8px">${userEmail}</td>
          </tr>
          <tr style="border-bottom:1px solid #e5e7eb">
            <td style="padding:8px;font-weight:600">Topic</td>
            <td style="padding:8px">${purpose}</td>
          </tr>
          <tr style="border-bottom:1px solid #e5e7eb">
            <td style="padding:8px;font-weight:600">Time</td>
            <td style="padding:8px">${preferredTime}</td>
          </tr>
          ${
            meetLink
              ? `<tr>
            <td style="padding:8px;font-weight:600">Google Meet</td>
            <td style="padding:8px"><a href="${meetLink}" style="color:#7c3aed">${meetLink}</a></td>
          </tr>`
              : ""
          }
        </table>
        <p>We look forward to connecting with you.</p>
        <p style="color:#7c3aed;font-weight:600">- Ilmora Studios Team</p>
      </div>
    </div>
  `;
}
