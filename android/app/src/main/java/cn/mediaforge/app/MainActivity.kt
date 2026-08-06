package cn.mediaforge.app

import android.app.Activity
import android.content.Intent
import android.content.SharedPreferences
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.DocumentsContract
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.view.ViewGroup
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.BaseAdapter
import android.widget.CheckBox
import android.widget.EditText
import android.widget.ListView
import android.widget.ProgressBar
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.button.MaterialButton
import com.google.android.material.tabs.TabLayout
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var prefs: SharedPreferences
    private var kind = Formats.VIDEO
    private val files = mutableListOf<String>()
    private val checked = mutableSetOf<String>()
    private val rowStatus = mutableMapOf<String, String>()
    private var outDir = ""
    private var busy = false
    private var encoders: Set<String> = emptySet()

    private lateinit var fileList: ListView
    private lateinit var adapter: FileAdapter
    private lateinit var spFmt: Spinner
    private lateinit var spVcodec: Spinner
    private lateinit var spAcodec: Spinner
    private lateinit var spPattern: Spinner
    private lateinit var spWorkers: Spinner
    private lateinit var form: ParamForm
    private lateinit var edOutdir: EditText
    private lateinit var progress: ProgressBar
    private lateinit var lblStatus: TextView
    private lateinit var btnStart: MaterialButton
    private lateinit var btnCancel: MaterialButton
    private lateinit var lblVcodec: TextView
    private lateinit var lblAcodec: TextView

    private val PATTERNS = listOf("{name}" to "原文件名", "{name}_converted" to "原文件名_converted",
        "{name}_{date}" to "原文件名_日期", "{parent}_{name}" to "上级目录_文件名")

    override fun onCreate(savedInstanceState: Bundle?) {
        prefs = getSharedPreferences("mediaforge", MODE_PRIVATE)
        applyThemeFromPrefs()
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        findViewById<MaterialToolbar>(R.id.toolbar).let {
            setSupportActionBar(it)
        }

        fileList = findViewById(R.id.file_list)
        spFmt = findViewById(R.id.sp_fmt)
        spVcodec = findViewById(R.id.sp_vcodec)
        spAcodec = findViewById(R.id.sp_acodec)
        spPattern = findViewById(R.id.sp_pattern)
        spWorkers = findViewById(R.id.sp_workers)
        form = findViewById(R.id.param_form)
        edOutdir = findViewById(R.id.ed_outdir)
        progress = findViewById(R.id.progress)
        lblStatus = findViewById(R.id.lbl_status)
        btnStart = findViewById(R.id.btn_start)
        btnCancel = findViewById(R.id.btn_cancel)
        lblVcodec = findViewById(R.id.lbl_vcodec)
        lblAcodec = findViewById(R.id.lbl_acodec)

        adapter = FileAdapter()
        fileList.adapter = adapter

        findViewById<MaterialButton>(R.id.btn_add).setOnClickListener { pickFiles() }
        findViewById<MaterialButton>(R.id.btn_remove).setOnClickListener { removeSelected() }
        findViewById<MaterialButton>(R.id.btn_clear).setOnClickListener {
            files.clear(); checked.clear(); rowStatus.clear(); adapter.notifyDataSetChanged(); updateCount()
        }
        findViewById<MaterialButton>(R.id.btn_browse).setOnClickListener { pickOutDir() }
        btnStart.setOnClickListener { start() }
        btnCancel.setOnClickListener {
            Converter.cancel()
            btnCancel.isEnabled = false
            lblStatus.text = "正在取消…"
        }

        findViewById<TabLayout>(R.id.tabs).let { tabs ->
            tabs.addTab(tabs.newTab().setText(R.string.tab_video))
            tabs.addTab(tabs.newTab().setText(R.string.tab_audio))
            tabs.addTab(tabs.newTab().setText(R.string.tab_image))
            tabs.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
                override fun onTabSelected(tab: TabLayout.Tab) {
                    val k = when (tab.position) { 0 -> Formats.VIDEO; 1 -> Formats.AUDIO; else -> Formats.IMAGE }
                    if (k != kind) applyKind(k)
                }
                override fun onTabUnselected(tab: TabLayout.Tab) {}
                override fun onTabReselected(tab: TabLayout.Tab) {}
            })
        }

        spFmt.onItemSelectedListener = sel { rebuildCodecsAndForm() }
        spVcodec.onItemSelectedListener = sel { rebuildForm() }
        spAcodec.onItemSelectedListener = sel { rebuildForm() }

        spPattern.setSelection(PATTERNS.indexOfFirst { it.first == prefs.getString("pattern", "{name}") }
            .coerceAtLeast(0))

        outDir = prefs.getString("out_dir", "") ?: ""
        edOutdir.setText(outDir)

        ensureStorage()
        applyKind(Formats.VIDEO)

        Converter.listener = object : Converter.Listener {
            override fun onProgress(job: Job, p: Float, speed: String) {
                runOnUiThread {
                    rowStatus[job.src] = "${(p * 100).toInt()}%"
                    adapter.notifyDataSetChanged()
                    progress.progress = (p * 100).toInt()
                    lblStatus.text = "${File(job.src).name} ${(p * 100).toInt()}%"
                }
            }

            override fun onJobDone(job: Job, ok: Boolean, message: String) {
                runOnUiThread {
                    rowStatus[job.src] = if (ok) "完成" else "失败"
                    if (!ok && message.isNotEmpty()) Toast.makeText(this@MainActivity,
                        "${File(job.src).name}: ${message.take(200)}", Toast.LENGTH_LONG).show()
                    adapter.notifyDataSetChanged()
                }
            }

            override fun onAllDone() {
                runOnUiThread {
                    setBusy(false)
                    progress.progress = 100
                    lblStatus.text = "全部完成"
                    val done = rowStatus.values.count { it == "完成" }
                    Toast.makeText(this@MainActivity, "转换完成：成功 $done 个", Toast.LENGTH_LONG).show()
                }
            }
        }

        Thread {
            encoders = Converter.availableEncoders()
            runOnUiThread { rebuildCodecsAndForm() }
        }.start()
    }

    private fun btnCancel() = R.id.btn_cancel

    private fun sel(fn: () -> Unit) = object : AdapterView.OnItemSelectedListener {
        override fun onItemSelected(p: AdapterView<*>?, v: View?, pos: Int, id: Long) { fn() }
        override fun onNothingSelected(p: AdapterView<*>?) {}
    }

    // ---------------- 主题 ----------------
    private fun applyThemeFromPrefs() {
        val dark = prefs.getBoolean("ui_dark", false)
        AppCompatDelegate.setDefaultNightMode(
            if (dark) AppCompatDelegate.MODE_NIGHT_YES else AppCompatDelegate.MODE_NIGHT_NO)
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menu.add(0, 1, 0, if (prefs.getBoolean("ui_dark", false))
            R.string.theme_toggle_night else R.string.theme_toggle)
            .setShowAsAction(MenuItem.SHOW_AS_ACTION_ALWAYS)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == 1) {
            val dark = !prefs.getBoolean("ui_dark", false)
            prefs.edit().putBoolean("ui_dark", dark).apply()
            applyThemeFromPrefs()   // 触发重建，立即生效
            return true
        }
        return super.onOptionsItemSelected(item)
    }

    // ---------------- 存储权限 ----------------
    private fun ensureStorage() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && !Environment.isExternalStorageManager()) {
            Toast.makeText(this, R.string.need_storage, Toast.LENGTH_LONG).show()
            runCatching {
                startActivity(Intent(android.provider.Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
            }
        }
    }

    // ---------------- 类别 / 格式 ----------------
    private fun applyKind(k: String) {
        kind = k
        val fmts = Formats.formatsFor(k)
        spFmt.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item,
            fmts.map { "${it.label}  (.${it.ext})" })
        rebuildCodecsAndForm()
        adapter.notifyDataSetChanged()
    }

    private fun currentFormat(): ContainerFormat? {
        val fmts = Formats.formatsFor(kind)
        return fmts.getOrNull(spFmt.selectedItemPosition)
    }

    private fun rebuildCodecsAndForm() {
        val fmt = currentFormat() ?: return
        val hasV = kind == Formats.VIDEO && fmt.videoCodecs.isNotEmpty()
        val hasA = fmt.audioCodecs.isNotEmpty() && kind != Formats.IMAGE
        lblVcodec.visibility = if (hasV) View.VISIBLE else View.GONE
        spVcodec.visibility = if (hasV) View.VISIBLE else View.GONE
        lblAcodec.visibility = if (hasA) View.VISIBLE else View.GONE
        spAcodec.visibility = if (hasA) View.VISIBLE else View.GONE
        if (hasV) spVcodec.adapter = codecAdapter(fmt.videoCodecs)
        if (hasA) spAcodec.adapter = codecAdapter(fmt.audioCodecs)
        rebuildForm()
    }

    private fun codecAdapter(pool: List<String>): ArrayAdapter<String> =
        ArrayAdapter(this, android.R.layout.simple_spinner_item, pool.map {
            if (it != "copy" && encoders.isNotEmpty() && it !in encoders)
                "$it${getString(R.string.not_installed)}" else it
        })

    private fun selectedCodec(sp: Spinner, pool: List<String>): String =
        pool.getOrNull(sp.selectedItemPosition) ?: ""

    private fun formParams(): List<Param> {
        if (kind == Formats.IMAGE) return Formats.IMAGE_PARAMS
        val fmt = currentFormat()
        val params = Formats.GENERAL_PARAMS + Formats.VIDEO_FILTER_PARAMS + Formats.AUDIO_FILTER_PARAMS
        val extra = mutableListOf<Param>()
        if (kind == Formats.VIDEO && fmt != null)
            extra += Formats.codecParams(selectedCodec(spVcodec, fmt.videoCodecs))
        if (fmt != null)
            extra += Formats.codecParams(selectedCodec(spAcodec, fmt.audioCodecs))
        val seen = LinkedHashMap<String, Param>()
        (params + extra).forEach { seen[it.key] = it }
        return seen.values.toList()
    }

    private fun rebuildForm() {
        form.setParams(formParams())
    }

    // ---------------- 文件 ----------------
    private fun pickFiles() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
            putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
        }
        startActivityForResult(intent, REQ_FILES)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != Activity.RESULT_OK || data == null) return
        when (requestCode) {
            REQ_FILES -> {
                val uris = mutableListOf<Uri>()
                val clip = data.clipData
                if (clip != null) for (i in 0 until clip.itemCount) uris += clip.getItemAt(i).uri
                else data.data?.let { uris += it }
                val paths = uris.mapNotNull { uriToPath(it) }
                addFiles(paths)
            }
            REQ_OUT_DIR -> {
                data.data?.let { uri ->
                    treeToPath(uri)?.let {
                        outDir = it
                        prefs.edit().putString("out_dir", it).apply()
                        edOutdir.setText(it)
                    }
                }
            }
        }
    }

    private fun uriToPath(uri: Uri): String? {
        try {
            contentResolver.query(uri, arrayOf("_data"), null, null, null)?.use { c ->
                if (c.moveToFirst()) {
                    val v = c.getString(0)
                    if (!v.isNullOrEmpty() && File(v).exists()) return v
                }
            }
        } catch (e: Exception) { /* fallthrough 到拷贝 */ }
        // 无法直接取路径：拷贝到缓存目录
        return try {
            val name = uri.lastPathSegment?.substringAfterLast('/') ?: "input_${System.currentTimeMillis()}"
            val out = File(cacheDir, name)
            contentResolver.openInputStream(uri).use { ins ->
                out.outputStream().use { outs -> ins?.copyTo(outs) }
            }
            out.absolutePath
        } catch (e: Exception) { null }
    }

    private fun treeToPath(uri: Uri): String? {
        var doc = DocumentsContract.getTreeDocumentId(uri)
        val path = uri.path ?: return null
        val treePart = path.substringAfter("tree/", "")
        return try {
            val decoded = Uri.decode(treePart)
            if (decoded.startsWith("primary:"))
                File(Environment.getExternalStorageDirectory(), decoded.removePrefix("primary:")).absolutePath
            else if (decoded.contains(':')) {
                val (vol, rel) = decoded.split(':', limit = 2)
                File("/storage/$vol", rel).absolutePath
            } else File("/storage/emulated/0", doc).absolutePath
        } catch (e: Exception) { null }
    }

    private fun addFiles(paths: List<String>) {
        val valid = paths.filter { p ->
            val ext = p.substringAfterLast('.', "").lowercase()
            ext in Formats.INPUT_VIDEO_EXT || ext in Formats.INPUT_AUDIO_EXT || ext in Formats.INPUT_IMAGE_EXT
        }
        if (valid.isEmpty()) {
            Toast.makeText(this, "没有找到可转换的媒体文件", Toast.LENGTH_SHORT).show()
            return
        }
        val firstKind = Formats.detectKind(valid.first())
        if (firstKind != kind) {
            findViewById<TabLayout>(R.id.tabs).selectTab(
                findViewById<TabLayout>(R.id.tabs).getTabAt(
                    when (firstKind) { Formats.VIDEO -> 0; Formats.AUDIO -> 1; else -> 2 }))
            applyKind(firstKind)
        }
        for (p in valid) if (p !in files) files += p
        adapter.notifyDataSetChanged()
        updateCount()
        Toast.makeText(this, "已添加 ${valid.size} 个文件", Toast.LENGTH_SHORT).show()
    }

    private fun removeSelected() {
        files.removeAll(checked)
        checked.clear()
        adapter.notifyDataSetChanged()
        updateCount()
    }

    private fun updateCount() {
        findViewById<TextView>(R.id.lbl_count).text =
            "${getString(R.string.file_list)} · ${files.size} 个文件"
    }

    private fun pickOutDir() {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT_TREE), REQ_OUT_DIR)
    }

    // ---------------- 转换 ----------------
    private fun collectParams(): MutableMap<String, Any?> {
        val p = Formats.defaultParamsFor(kind)
        p.putAll(form.values())
        val fmt = currentFormat()
        if (kind == Formats.VIDEO && fmt != null)
            p["video_codec"] = selectedCodec(spVcodec, fmt.videoCodecs)
        if (fmt != null && fmt.audioCodecs.isNotEmpty() && kind != Formats.IMAGE)
            p["audio_codec"] = selectedCodec(spAcodec, fmt.audioCodecs)
        p["overwrite"] = findViewById<CheckBox>(R.id.chk_overwrite).isChecked
        return p
    }

    private fun buildOutputPath(src: String, ext: String): String {
        val name = File(src).name.substringBeforeLast('.')
        val date = SimpleDateFormat("yyyyMMdd", Locale.getDefault()).format(Date())
        val parent = File(src).parentFile?.name ?: ""
        val pattern = PATTERNS.getOrNull(spPattern.selectedItemPosition)?.first ?: "{name}"
        val base = pattern.replace("{name}", name).replace("{date}", date).replace("{parent}", parent)
        val dir = outDir.ifEmpty { File(src).parent ?: "." }
        var out = File(dir, "$base.$ext")
        val overwrite = findViewById<CheckBox>(R.id.chk_overwrite).isChecked
        var i = 1
        while (out.exists() && !overwrite) {
            out = File(dir, "${base}($i).$ext")
            i++
        }
        return out.absolutePath
    }

    private fun start() {
        if (files.isEmpty()) {
            Toast.makeText(this, R.string.no_files, Toast.LENGTH_SHORT).show()
            return
        }
        val fmt = currentFormat() ?: return
        val params = collectParams()
        val jobs = files.map { src -> Job(src, buildOutputPath(src, fmt.ext), params.toMap(), kind) }
        rowStatus.clear()
        files.forEach { rowStatus[it] = "等待中" }
        adapter.notifyDataSetChanged()
        setBusy(true)
        progress.progress = 0
        lblStatus.text = "开始转换 ${jobs.size} 个文件…"
        val workers = (spWorkers.selectedItem as? String)?.toIntOrNull() ?: 1
        Converter.start(jobs, workers)
        prefs.edit().putString("pattern", PATTERNS.getOrNull(spPattern.selectedItemPosition)?.first).apply()
    }

    private fun setBusy(b: Boolean) {
        busy = b
        btnStart.isEnabled = !b
        btnStart.text = if (b) getString(R.string.converting) else getString(R.string.start_convert)
        btnCancel.isEnabled = b
        form.setEnabledAll(!b)
        spFmt.isEnabled = !b
        spVcodec.isEnabled = !b
        spAcodec.isEnabled = !b
    }

    // ---------------- 列表适配器 ----------------
    private inner class FileAdapter : BaseAdapter() {
        override fun getCount() = files.size
        override fun getItem(position: Int) = files[position]
        override fun getItemId(position: Int) = position.toLong()

        override fun getView(position: Int, convertView: View?, parent: ViewGroup?): View {
            val view = convertView ?: layoutInflater.inflate(R.layout.item_file, parent, false)
            val path = files[position]
            val check = view.findViewById<CheckBox>(R.id.row_check)
            val name = view.findViewById<TextView>(R.id.row_name)
            val status = view.findViewById<TextView>(R.id.row_status)
            name.text = File(path).name
            status.text = rowStatus[path] ?: ""
            check.setOnCheckedChangeListener(null)
            check.isChecked = path in checked
            check.setOnCheckedChangeListener { _, isChecked ->
                if (isChecked) checked += path else checked -= path
            }
            return view
        }
    }

    companion object {
        private const val REQ_FILES = 1001
        private const val REQ_OUT_DIR = 1002
    }
}
