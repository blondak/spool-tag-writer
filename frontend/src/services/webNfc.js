const readRecordBytes = async (record) => {
  if (record.data instanceof DataView) {
    return new Uint8Array(record.data.buffer, record.data.byteOffset, record.data.byteLength);
  }

  if (record.data?.arrayBuffer) {
    return new Uint8Array(await record.data.arrayBuffer());
  }

  throw new Error("The browser did not expose NFC record bytes.");
};

export const readTagViaWebNfc = async () => {
  const ndef = new window.NDEFReader();

  return new Promise((resolve, reject) => {
    const cleanup = () => {
      ndef.removeEventListener("reading", onReading);
      ndef.removeEventListener("readingerror", onReadingError);
    };

    const onReading = async (event) => {
      try {
        for (const record of event.message.records) {
          if (record.recordType !== "mime" || record.mediaType !== "application/json") {
            continue;
          }

          const payloadBytes = await readRecordBytes(record);
          const payloadText = new TextDecoder().decode(payloadBytes);
          let payloadJson = null;

          try {
            payloadJson = JSON.parse(payloadText);
          } catch {
            payloadJson = null;
          }

          cleanup();
          resolve({
            status: "ok",
            mime_type: record.mediaType,
            payload_size: payloadBytes.byteLength,
            payload_text: payloadText,
            payload_json: payloadJson,
          });
          return;
        }

        cleanup();
        reject(new Error("The tag does not contain an application/json MIME record."));
      } catch (error) {
        cleanup();
        reject(error);
      }
    };

    const onReadingError = () => {
      cleanup();
      reject(new Error("Failed to read the NFC tag."));
    };

    ndef.addEventListener("reading", onReading);
    ndef.addEventListener("readingerror", onReadingError);
    ndef.scan().catch((error) => {
      cleanup();
      reject(error);
    });
  });
};

export const writeTagViaWebNfc = async (preparedPreview) => {
  const payloadText = preparedPreview.payload_json;
  const payloadBytes = new TextEncoder().encode(payloadText);
  const ndef = new window.NDEFReader();

  await ndef.write({
    records: [
      {
        recordType: "mime",
        mediaType: "application/json",
        data: payloadBytes,
      },
    ],
  });

  return {
    status: "written",
    mime_type: "application/json",
    payload_size: payloadBytes.byteLength,
    payload_text: payloadText,
    payload_json: preparedPreview.payload,
    spool_id: preparedPreview.spool?.id,
  };
};
