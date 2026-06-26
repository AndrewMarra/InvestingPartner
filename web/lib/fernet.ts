// Fernet encryption in pure Node crypto — produces tokens the Python
// `cryptography` library decrypts. Server-only; the master key never reaches
// the browser. Used to encrypt users' BYOK keys before they hit the database.
import crypto from "crypto";

function b64urlDecode(s: string): Buffer {
  return Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64");
}
function b64urlEncode(b: Buffer): string {
  return b.toString("base64").replace(/\+/g, "-").replace(/\//g, "_");
}

export function fernetEncrypt(message: string, masterKey: string): string {
  const key = b64urlDecode(masterKey);
  if (key.length !== 32) throw new Error("MASTER_ENCRYPTION_KEY must be a 32-byte urlsafe base64 key");
  const signingKey = key.subarray(0, 16);
  const encKey = key.subarray(16, 32);

  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv("aes-128-cbc", encKey, iv); // PKCS7 padding on
  const ciphertext = Buffer.concat([cipher.update(Buffer.from(message, "utf8")), cipher.final()]);

  const ts = Buffer.alloc(8);
  ts.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 1000)));

  const body = Buffer.concat([Buffer.from([0x80]), ts, iv, ciphertext]);
  const hmac = crypto.createHmac("sha256", signingKey).update(body).digest();
  return b64urlEncode(Buffer.concat([body, hmac]));
}
