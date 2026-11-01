package app.vboard

import okhttp3.Call
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Minimal OkHttp client for `POST {baseUrl}/v1/process` (multipart) and
 * `POST {baseUrl}/v1/agent` (JSON `{content, device_id}`, never `languages`).
 * Network only; parsing lives in [ProcessResponseParser]/[AgentResponseParser].
 * Call [cancel] to abort an in-flight request (IME view going away).
 */
class BackendClient(baseUrl: String, client: OkHttpClient? = null) {

    private val endpoint: String = baseUrl.trimEnd('/') + PATH
    private val agentEndpoint: String = baseUrl.trimEnd('/') + PATH_AGENT
    private val http: OkHttpClient = client ?: OkHttpClient.Builder()
        .connectTimeout(CONNECT_TIMEOUT_MS, TimeUnit.MILLISECONDS)
        .callTimeout(CALL_TIMEOUT_MS, TimeUnit.MILLISECONDS)
        .build()
    private val agentHttp: OkHttpClient = client ?: OkHttpClient.Builder()
        .connectTimeout(CONNECT_TIMEOUT_MS, TimeUnit.MILLISECONDS)
        .callTimeout(CALL_TIMEOUT_AGENT_MS, TimeUnit.MILLISECONDS)
        .build()

    @Volatile
    private var active: Call? = null

    data class Result(val httpCode: Int, val body: String)

    /** Blocking; call off the main thread. */
    @Throws(IOException::class)
    fun processAudio(
        wav: ByteArray,
        languages: String,
        contextText: String,
        deviceId: String,
    ): Result {
        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart(PART_AUDIO, AUDIO_FILE_NAME, wav.toRequestBody(AUDIO_MEDIA_TYPE))
            .addFormDataPart(PART_LANGUAGES, languages)
            .addFormDataPart(PART_DEVICE_ID, deviceId)
            .apply { if (contextText.isNotEmpty()) addFormDataPart(PART_CONTEXT, contextText) }
            .build()
        val call = http.newCall(Request.Builder().url(endpoint).post(form).build())
        active = call
        try {
            call.execute().use { response ->
                val body = try {
                    response.body?.string() ?: ""
                } catch (_: IOException) {
                    ""
                }
                return Result(response.code, body)
            }
        } finally {
            active = null
        }
    }

    fun cancel() {
        active?.cancel()
    }

    /** Blocking; call off the main thread. Sends `{content, device_id}` only. */
    @Throws(IOException::class)
    fun agent(content: String, deviceId: String): Result {
        val payload = JSONObject().put("content", content).put("device_id", deviceId).toString()
        val call = agentHttp.newCall(
            Request.Builder().url(agentEndpoint).post(payload.toRequestBody(JSON_MEDIA_TYPE)).build(),
        )
        active = call
        try {
            call.execute().use { response ->
                val body = try {
                    response.body?.string() ?: ""
                } catch (_: IOException) {
                    ""
                }
                return Result(response.code, body)
            }
        } finally {
            active = null
        }
    }

    companion object {
        const val PATH = "/v1/process"
        const val PATH_AGENT = "/v1/agent"
        const val CONNECT_TIMEOUT_MS = 5_000L
        const val CALL_TIMEOUT_MS = 20_000L
        const val CALL_TIMEOUT_AGENT_MS = 25_000L
        const val PART_AUDIO = "audio"
        const val PART_LANGUAGES = "languages"
        const val PART_CONTEXT = "context_text"
        const val PART_DEVICE_ID = "device_id"
        const val AUDIO_FILE_NAME = "recording.wav"
        private val AUDIO_MEDIA_TYPE = "audio/x-wav".toMediaType()
        private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
    }
}
