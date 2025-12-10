const fs = require('fs');
const crypto = require('crypto');
const path = require('path');
const { S3Client, PutObjectCommand, HeadObjectCommand, GetObjectCommand } = require("@aws-sdk/client-s3");

// --- CONFIGURATION ---
// Set this to TRUE if you don't have R2 keys yet and just want to test logic locally
const LOCAL_MODE = true;

// R2 / S3 Configuration
const R2_ACCOUNT_ID = "YOUR_CLOUDFLARE_ACCOUNT_ID";
const ACCESS_KEY_ID = "YOUR_ACCESS_KEY_ID";
const SECRET_ACCESS_KEY = "YOUR_SECRET_ACCESS_KEY";
const BUCKET_NAME = "my-chat-assets";

// Initialize S3 Client (R2 uses the S3 protocol)
const s3 = new S3Client({
    region: "auto",
    endpoint: `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
    credentials: {
        accessKeyId: ACCESS_KEY_ID,
        secretAccessKey: SECRET_ACCESS_KEY,
    },
});

// --- CORE LOGIC: CONTENT ADDRESSING ---

/**
 * 1. Calculate the Hash (CID) of a file
 * This is the "Fingerprint" of the data.
 */
function calculateHash(buffer) {
    return crypto.createHash('sha256').update(buffer).digest('hex');
}

/**
 * 2. Upload Function
 * Returns the HASH (The Content ID), not a URL.
 */
async function uploadFile(filePath) {
    const fileBuffer = fs.readFileSync(filePath);
    const fileHash = calculateHash(fileBuffer);
    const fileExtension = path.extname(filePath);

    // The "Key" (Filename) in the bucket is the HASH itself.
    // e.g., "a1b2c3d4e5..."
    const objectKey = `${fileHash}${fileExtension}`;

    console.log(`[+] Processing: ${path.basename(filePath)}`);
    console.log(`    Hash (CID): ${fileHash}`);

    if (LOCAL_MODE) {
        // Simulation for testing without R2
        const localDir = './local_storage';
        if (!fs.existsSync(localDir)) fs.mkdirSync(localDir);

        const localFilePath = `${localDir}/${objectKey}`;
        if (fs.existsSync(localFilePath)) {
            console.log(`    [Skipped]: Content already exists locally! Returning existing Hash.`);
            return objectKey;
        }

        fs.writeFileSync(localFilePath, fileBuffer);
        console.log(`    [Saved Locally]: ${objectKey}`);
        return objectKey;
    }

    // CHECK if file already exists (Deduplication)
    try {
        await s3.send(new HeadObjectCommand({ Bucket: BUCKET_NAME, Key: objectKey }));
        console.log(`    [Skipped]: Content already exists on R2! Returning existing Hash.`);
        return objectKey;
    } catch (err) {
        // If error is "NotFound", we proceed to upload.
        if (err.name !== "NotFound") {
            // If it's a simulated 404 for this logic
        }
    }

    // UPLOAD if new
    try {
        await s3.send(new PutObjectCommand({
            Bucket: BUCKET_NAME,
            Key: objectKey,
            Body: fileBuffer,
            ContentType: getContentType(fileExtension)
        }));
        console.log(`    [Uploaded]: Success! stored at ${objectKey}`);
        return objectKey;
    } catch (err) {
        console.error("Upload Failed:", err);
    }
}

/**
 * 3. Retrieval Function
 * Uses the HASH to find the file.
 */
async function downloadFile(objectKey) {
    console.log(`\n[<] Retrieving Content: ${objectKey}`);

    if (LOCAL_MODE) {
        const localData = fs.readFileSync(`./local_storage/${objectKey}`);
        console.log(`    [Found Local]: ${localData.length} bytes`);
        return;
    }

    try {
        const data = await s3.send(new GetObjectCommand({
            Bucket: BUCKET_NAME,
            Key: objectKey
        }));
        // In a real app, we would pipe this stream to the browser
        console.log(`    [Found R2]: File stream ready.`);
    } catch (err) {
        console.error("    [Error]: File not found on network.");
    }
}

// Helper for MIME types
function getContentType(ext) {
    const types = { '.jpg': 'image/jpeg', '.png': 'image/png', '.txt': 'text/plain' };
    return types[ext] || 'application/octet-stream';
}

// --- RUNNER ---
(async () => {
    // Create a dummy file to test
    const testFileName = "test_image.txt";
    fs.writeFileSync(testFileName, "This is a decentralized meme.");

    // 1. User A uploads the file
    console.log("--- User A Uploading ---");
    const cid = await uploadFile(testFileName);

    // 2. User B tries to upload the SAME file (Simulating viral content)
    console.log("\n--- User B Uploading Same Content ---");
    await uploadFile(testFileName);

    // 3. User C downloads it using ONLY the Hash
    await downloadFile(cid);
})();