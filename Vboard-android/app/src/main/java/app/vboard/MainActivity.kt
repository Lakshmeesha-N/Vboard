package app.vboard

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var store: SettingsStore
    private lateinit var saveLangsButton: Button
    private lateinit var langsStatus: TextView
    private val langBoxes = mutableMapOf<String, CheckBox>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        store = SettingsStore(this)

        findViewById<Button>(R.id.btn_enable).setOnClickListener {
            startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
        }
        findViewById<Button>(R.id.btn_choose).setOnClickListener {
            (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager)
                .showInputMethodPicker()
        }

        findViewById<Button>(R.id.btn_mic).setOnClickListener { requestMic() }
        findViewById<Button>(R.id.btn_app_settings).setOnClickListener { openAppSettings() }

        buildLanguageList()
        saveLangsButton = findViewById(R.id.btn_save_langs)
        langsStatus = findViewById(R.id.tv_langs_status)
        saveLangsButton.setOnClickListener { saveLanguages() }

        val urlField = findViewById<EditText>(R.id.et_backend_url)
        if (urlField.text.isEmpty()) urlField.setText(store.getBackendUrl())
        val urlStatus = findViewById<TextView>(R.id.tv_url_status)
        findViewById<Button>(R.id.btn_save_url).setOnClickListener {
            if (store.setBackendUrl(urlField.text.toString())) {
                urlStatus.text = "Saved."
            } else {
                urlStatus.text = "Enter a URL starting with http:// or https://."
            }
        }

        refreshMicUi()
        refreshLangsUi()
    }

    override fun onResume() {
        super.onResume()
        refreshMicUi()
    }

    private fun buildLanguageList() {
        val container = findViewById<LinearLayout>(R.id.langs_container)
        val saved = store.getLanguages().toSet()
        for (name in LanguageList.pickerOrder()) {
            val box = CheckBox(this)
            box.text = name
            box.isChecked = name in saved
            box.setOnCheckedChangeListener { _, _ -> refreshLangsUi() }
            langBoxes[name] = box
            container.addView(box)
        }
    }

    private fun currentSelection(): List<String> =
        LanguageList.pickerOrder().filter { langBoxes[it]?.isChecked == true }

    private fun refreshLangsUi() {
        val sel = currentSelection()
        saveLangsButton.isEnabled = LanguageList.isValid(sel)
        val atMax = LanguageList.isAtMax(sel)
        for ((name, box) in langBoxes) {
            box.isEnabled = name in sel || !atMax
        }
        langsStatus.text = when {
            atMax -> "Maximum 5 languages. Untick one to choose another."
            store.hasLanguages() -> "Saved: ${store.getLanguagesCsv()}"
            else -> "Pick 1 to 5 languages, then save."
        }
    }

    private fun saveLanguages() {
        if (store.setLanguagesCsv(LanguageList.format(currentSelection()))) {
            langsStatus.text = "Saved: ${store.getLanguagesCsv()}"
        } else {
            langsStatus.text = "Pick 1 to 5 languages."
        }
    }

    private fun micGranted(): Boolean = ContextCompat.checkSelfPermission(
        this, Manifest.permission.RECORD_AUDIO
    ) == PackageManager.PERMISSION_GRANTED

    private fun requestMic() {
        if (micGranted()) {
            refreshMicUi()
            return
        }
        store.setMicRequested()
        ActivityCompat.requestPermissions(
            this, arrayOf(Manifest.permission.RECORD_AUDIO), MIC_REQUEST
        )
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == MIC_REQUEST) refreshMicUi()
    }

    private fun refreshMicUi() {
        val status = findViewById<TextView>(R.id.tv_mic_status)
        val appSettings = findViewById<Button>(R.id.btn_app_settings)
        if (micGranted()) {
            status.text = "Microphone: granted."
            appSettings.visibility = View.GONE
            return
        }
        val blocked = store.wasMicRequested() &&
            !ActivityCompat.shouldShowRequestPermissionRationale(
                this, Manifest.permission.RECORD_AUDIO
            )
        status.text = if (blocked) {
            "Microphone: blocked. Open Settings to allow it."
        } else {
            "Microphone: not granted."
        }
        appSettings.visibility = if (blocked) View.VISIBLE else View.GONE
    }

    private fun openAppSettings() {
        startActivity(
            Intent(
                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.fromParts("package", packageName, null)
            )
        )
    }

    companion object {
        private const val MIC_REQUEST = 41
    }
}
