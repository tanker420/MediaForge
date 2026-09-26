package cn.mediaforge.app

import android.app.Activity
import android.content.Intent
import android.content.SharedPreferences
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.DocumentsContract
import android.view.View
import android.view.ViewGroup
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.SeekBar
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.button.MaterialButton
import com.google.android.material.color.MaterialColors
import com.google.android.material.materialswitch.MaterialSwitch
import com.google.android.material.tabs.TabLayout
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var prefs: SharedPreferences
    private var kind = Formats.VIDEO
    private val files = mutableListOf<String>()
    private val rowStatus = mutableMapOf<String, String>()
    private val rowProgress = mutableMapOf<String, Int>()
    private var outDir = ""
    private var busy = false
    private var encoders: Set<String> = emptySet()

    private lateinit var fileList: RecyclerView
    private lateinit var adapter: FileAdapter
    private lateinit var spFmt: Spinner
    private lateinit var spVcodec: Spinner
    private lateinit var spAcodec: Spinner
    private lateinit var spPattern: Spinner
    private lateinit var spPreset: Spinner
    private lateinit var edPattern: android.widget.EditText
    private lateinit var skWorkers: SeekBar
    private lateinit var lblWorkers: TextView
    private lateinit var form: ParamForm
    private lateinit var edOutdir: android.widget.EditText
    private lateinit var progress: ProgressBar
    private lateinit var lblStatus: TextView
    private lateinit var btnStart: MaterialButton
    private lateinit var btnCancel: MaterialButton
    private lateinit var lblVcodec: TextView
    private lateinit var lblAcodec: TextView
    private lateinit var lblEmpty: TextView
    private lateinit var chkOverwrite: MaterialSwitch
    private var presetPool: List<Preset> = emptyList()

    private val PATTERNS = listOf("{name}" to "原文件名", "{name}_converted" to "原文件名_converted",
        "{name}_{date}" to "原文件名_日期", "{parent}_{name}" to "上级目录_文件名")

    override fun onCreate(savedInstanceState: Bundle?) {
        prefs = getSharedPreferences("mediaforge", MODE_PRIVATE)
        applyThemeFromPrefs()
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        setContentView(R.layout.activity_main)

        // 工具栏
        val toolbar = findViewById<MaterialToolbar>(R.id.toolbar)
        setSupportActionBar(toolbar)
        toolbar.inflateMenu(R.menu.main_menu)
        toolbar.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.action_theme -> { toggleTheme(); true }
                R.id.action_update -> { checkUpdate(manual = true); true }
                R.id.action_about -> { showAbout(); true }
                else -> false
            }
        }

        // 状态栏内边距给 AppBar
        val appBar = findViewById<View>(R.id.toolbar).parent as? View
        appBar?.let {
            val top = it.paddingTop
            ViewCompat.setOnApplyWindowInsetsListener(it) { v, insets ->
                v.setPadding(v.paddingLeft,
                    top + insets.getInsets(WindowInsetsCompat.Type.statusBars()).top,
                    v.paddingRight, v.paddingBottom)
                insets
            }
        }
        // 底栏吃导航栏 inset
        val footer = findViewById<View>(R.id.footer_bar)
        val footerBottom = footer.paddingBottom
        ViewCompat.setOnApplyWindowInsetsListener(footer) { v, insets ->
            v.setPadding(v.paddingLeft, v.paddingTop, v.paddingRight,
                footerBottom + insets.getInsets(WindowInsetsCompat.Type.navigationBars()).bottom)
            insets
        }

        findViewById<TabLayout>(R.id.tabs).let {
            it.setBackgroundColor(MaterialColors.getColor(
                it, com.google.android.material.R.attr.colorSurface))
            it.setTabTextColors(
                MaterialColors.getColor(it, com.google.android.material.R.attr.colorOnSurfaceVariant),
                MaterialColors.getColor(it, com.google.android.material.R.attr.colorPrimary))
            it.setSelectedTabIndicatorColor(
                MaterialColors.getColor(it, com.google.android.material.R.attr.colorPrimary))
        }

        fileList = findViewById(R.id.file_list)
        spFmt = findViewById(R.id.sp_fmt)
        spVcodec = findViewById(R.id.sp_vcodec)
        spAcodec = findViewById(R.id.sp_acodec)
        spPattern = findViewById(R.id.sp_pattern)
        spPreset = findViewById(R.id.sp_preset)
        edPattern = findViewById(R.id.ed_pattern)
        skWorkers = findViewById(R.id.sk_workers)
        lblWorkers = findViewById(R.id.lbl_workers)
        form = findViewById(R.id.param_form)
        edOutdir = findViewById(R.id.ed_outdir)
        progress = findViewById(R.id.progress)
        lblStatus = findViewById(R.id.lbl_status)
        btnStart = findViewById(R.id.btn_start)
        btnCancel = findViewById(R.id.btn_cancel)
        lblVcodec = findViewById(R.id.lbl_vcodec)
        lblAcodec = findViewById(R.id.lbl_acodec)
        lblEmpty = findViewById(R.id.lbl_empty)
        chkOverwrite = findViewById(R.id.chk_overwrite)

        // RecyclerView 文件列表
        adapter = FileAdapter(
            onToggle = { path, checked ->
                if (checked) adapterCheckedAdd(path) else adapterCheckedRemove(path)
            },
            onClick = { /* 预留：点击条目可弹出详情/移除 */ }
        )
        fileList.layoutManager = LinearLayoutManager(this)
        fileList.adapter = adapter

        findViewById<com.google.android.material.floatingactionbutton.FloatingActionButton>(
            R.id.btn_add).setOnClickListener { pickFiles() }
        findViewById<MaterialButton>(R.id.btn_remove).setOnClickListener { removeSelected() }
        findViewById<MaterialButton>(R.id.btn_clear).setOnClickListener {
            files.clear(); adapter.setChecked(emptySet())
            rowStatus.clear(); rowProgress.clear()
            submitList(); updateCount()
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

        Presets.init(applicationContext)
        spPreset.onItemSelectedListener = sel { onPresetSelected() }
        findViewById<MaterialButton>(R.id.btn_presets).setOnClickListener { openPresetManager() }

        // 命名规则
        spPattern.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item,
            PATTERNS.map { it.second } + getString(R.string.custom_option))
        spPattern.onItemSelectedListener = sel {
            edPattern.visibility =
                if (spPattern.selectedItemPosition in PATTERNS.indices) View.GONE else View.VISIBLE
        }
        val savedPattern = prefs.getString("pattern", "{name}") ?: "{name}"
        val pi = PATTERNS.indexOfFirst { it.first == savedPattern }
        if (pi >= 0) spPattern.setSelection(pi)
        else {
            spPattern.setSelection(PATTERNS.size)
            edPattern.setText(savedPattern)
            edPattern.visibility = View.VISIBLE
        }

        // 并行任务滑块
        skWorkers.progress = (prefs.getInt("workers", 2) - 1).coerceIn(0, 7)
        lblWorkers.text = (skWorkers.progress + 1).toString()
        skWorkers.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(s: SeekBar?, p: Int, fromUser: Boolean) {
                lblWorkers.text = (p + 1).toString()
                if (fromUser) prefs.edit().putInt("workers", p + 1).apply()
            }
            override fun onStartTrackingTouch(s: SeekBar?) {}
            override fun onStopTrackingTouch(s: SeekBar?) {}
        })

        chkOverwrite.isChecked = prefs.getBoolean("overwrite", true)
        chkOverwrite.setOnCheckedChangeListener { _, v ->
            prefs.edit().putBoolean("overwrite", v).apply()
        }

        outDir = prefs.getString("out_dir", "") ?: ""
        edOutdir.setText(outDir)

        ensureStorage()
        applyKind(Formats.VIDEO)
        submitList()

        Converter.listener = object : Converter.Listener {
            override fun onProgress(job: Job, p: Float, speed: String) {
                runOnUiThread {
                    val pct = (p * 100).toInt()
                    rowStatus[job.src] = "$pct%"
                    rowProgress[job.src] = pct
                    updateItem(job.src)
                    progress.progress = pct
                    lblStatus.text = "${File(job.src).name} $pct%"
                }
            }

            override fun onJobDone(job: Job, ok: Boolean, message: String) {
                runOnUiThread {
                    rowStatus[job.src] = if (ok) "完成" else "失败"
                    rowProgress[job.src] = if (ok) 100 else -1
                    updateItem(job.src)
                    if (!ok && message.isNotEmpty()) Toast.makeText(this@MainActivity,
                        "${File(job.src).name}: ${message.take(200)}", Toast.LENGTH_LONG).show()
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

        maybeCheckUpdate()
    }

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

    private fun toggleTheme() {
        val dark = !prefs.getBoolean("ui_dark", false)
        prefs.edit().putBoolean("ui_dark", dark).apply()
        applyThemeFromPrefs()
    }

    private fun showAbout() {
        AlertDialog.Builder(this)
            .setTitle(R.string.app_name)
            .setMessage("v${currentVersion()}\n\n媒体格式批量转换工具\n基于 FFmpeg Kit\n\nhttps://github.com/tanker420/MediaForge")
            .setPositiveButton("确定", null)
            .show()
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

    // ---------------- 检查更新 ----------------
    private fun currentVersion(): String = runCatching {
        packageManager.getPackageInfo(packageName, 0).versionName ?: "0.0.0"
    }.getOrDefault("0.0.0")

    private fun maybeCheckUpdate() {
        val last = prefs.getLong("last_update_check", 0L)
        if (System.currentTimeMillis() - last < 24L * 60 * 60 * 1000) return
        checkUpdate(manual = false)
    }

    private fun checkUpdate(manual: Boolean) {
        prefs.edit().putLong("last_update_check", System.currentTimeMillis()).apply()
        val cur = currentVersion()
        Thread {
            val info = Updater.checkForUpdate(cur)
            runOnUiThread {
                if (info == null) {
                    if (manual) Toast.makeText(this, "已是最新版本", Toast.LENGTH_SHORT).show()
                    return@runOnUiThread
                }
                showUpdateDialog(info, cur)
            }
        }.start()
    }

    private fun showUpdateDialog(info: UpdateInfo, current: String) {
        val body = stripMarkdown(info.body).trim().ifBlank { "（无更新说明）" }
        AlertDialog.Builder(this)
            .setTitle("发现新版本 v${info.version}")
            .setMessage("当前版本：v$current\n\n${body.take(600)}")
            .setPositiveButton("立即更新") { _, _ -> startDownload(info) }
            .setNeutralButton("打开发布页") { _, _ -> openInBrowser(info.htmlUrl) }
            .setNegativeButton("稍后再说", null)
            .show()
    }

    private fun stripMarkdown(s: String): String =
        s.replace(Regex("!\\[[^\\]]*\\]\\([^)]*\\)"), "")
            .replace(Regex("\\[([^\\]]+)\\]\\([^)]*\\)"), "$1")
            .replace(Regex("`([^`]*)`"), "$1")
            .replace(Regex("(?m)^#{1,6}\\s+"), "")
            .replace(Regex("(?m)^\\s*[-*+]\\s+"), "• ")
            .replace(Regex("\\*\\*([^*]+)\\*\\*"), "$1")
            .replace(Regex("\\*([^*]+)\\*"), "$1")
            .replace(Regex("~~([^~]+)~~"), "$1")

    private fun openInBrowser(url: String) {
        if (url.isEmpty()) return
        runCatching { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
    }

    private fun startDownload(info: UpdateInfo) {
        val lbl = TextView(this).apply {
            text = "0%"
            textSize = 12f
            setPadding(0, dp(8), 0, dp(6))
        }
        val bar = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 100
            progress = 0
        }
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(10), dp(20), 0)
            addView(lbl)
            addView(bar)
        }
        val dlg = AlertDialog.Builder(this)
            .setTitle("正在下载 v${info.version}")
            .setView(box)
            .setCancelable(false)
            .create()
        dlg.show()

        Thread {
            val file = Updater.download(this, info) { done, total ->
                runOnUiThread {
                    val pct = if (total > 0) (done * 100 / total).toInt().coerceIn(0, 100) else 0
                    bar.progress = pct
                    lbl.text = if (total > 0) "$pct%" else "${done / 1024} KB"
                }
            }
            runOnUiThread {
                dlg.dismiss()
                if (file == null) {
                    Toast.makeText(this, "下载失败，请稍后重试", Toast.LENGTH_LONG).show()
                } else {
                    Updater.installApk(this, file)
                }
            }
        }.start()
    }

    // ---------------- 类别 / 格式 ----------------
    private fun applyKind(k: String) {
        kind = k
        val fmts = Formats.formatsFor(k)
        spFmt.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item,
            fmts.map { "${it.label}  (.${it.ext})" })
        refreshPresetSpinner()
        rebuildCodecsAndForm()
        submitList()
    }

    // ---------------- 预设 ----------------
    private fun refreshPresetSpinner() {
        presetPool = Presets.allPresets(kind)
        spPreset.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item,
            listOf(getString(R.string.custom_option)) + presetPool.map { it.name })
        spPreset.setSelection(0)
    }

    private fun onPresetSelected() {
        val pos = spPreset.selectedItemPosition
        if (pos <= 0) return
        val p = presetPool.getOrNull(pos - 1) ?: return
        if (p.kind != kind) {
            spPreset.setSelection(0)
            return
        }
        applyPreset(p)
    }

    private fun applyPreset(p: Preset) {
        val fi = Formats.formatsFor(kind).indexOfFirst { it.ext == p.ext }
        if (fi >= 0) spFmt.setSelection(fi)
        spFmt.post {
            currentFormat()?.let { fmt ->
                (p.params["video_codec"] as? String)?.let {
                    val i = fmt.videoCodecs.indexOf(it); if (i >= 0) spVcodec.setSelection(i)
                }
                (p.params["audio_codec"] as? String)?.let {
                    val i = fmt.audioCodecs.indexOf(it); if (i >= 0) spAcodec.setSelection(i)
                }
            }
            spVcodec.post {
                form.setValues(p.params)
                Toast.makeText(this, "已应用预设「${p.name}」，可继续微调",
                    Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun makeCurrentPresetParams(): MutableMap<String, Any?> {
        val p = collectParams()
        p.remove("overwrite")
        p["ext"] = currentFormat()?.ext ?: "mp4"
        return p
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
        val filters = if (kind == Formats.AUDIO) Formats.AUDIO_FILTER_PARAMS
        else Formats.VIDEO_FILTER_PARAMS + Formats.AUDIO_FILTER_PARAMS
        val params = Formats.GENERAL_PARAMS + filters
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
                resolveUrisAsync(uris)
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
            REQ_EXPORT -> {
                data.data?.let { uri ->
                    val ok = runCatching {
                        contentResolver.openOutputStream(uri)?.use {
                            it.write(Presets.exportPresets(Presets.loadUserPresets())
                                .toByteArray(Charsets.UTF_8))
                        }
                    }.isSuccess
                    Toast.makeText(this, if (ok) "预设已导出" else "导出失败",
                        Toast.LENGTH_SHORT).show()
                }
            }
            REQ_IMPORT -> {
                data.data?.let { uri ->
                    val text = runCatching {
                        contentResolver.openInputStream(uri)?.use {
                            String(it.readBytes(), Charsets.UTF_8)
                        } ?: ""
                    }.getOrNull()
                    if (text == null) {
                        Toast.makeText(this, "导入失败：无法读取文件", Toast.LENGTH_SHORT).show()
                        return@let
                    }
                    try {
                        val (n, skipped) = Presets.importPresets(text)
                        refreshPresetSpinner()
                        Toast.makeText(this, "导入 $n 个预设" +
                            (if (skipped.isNotEmpty()) "，跳过 ${skipped.size} 个同名/无效项" else ""),
                            Toast.LENGTH_LONG).show()
                    } catch (e: IllegalArgumentException) {
                        Toast.makeText(this, e.message ?: "导入失败", Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
    }

    /** 后台解析 SAF Uri → 本地路径（无法取路径时需要拷贝，可能很慢，必须在后台线程）。 */
    private fun resolveUrisAsync(uris: List<Uri>) {
        if (uris.isEmpty()) return
        val dlg = AlertDialog.Builder(this)
            .setMessage("正在导入文件…")
            .setCancelable(false)
            .create()
        dlg.show()
        Thread {
            val paths = uris.mapNotNull { uriToPath(it) }
            runOnUiThread {
                dlg.dismiss()
                if (paths.isEmpty()) {
                    Toast.makeText(this, "无法导入所选文件", Toast.LENGTH_SHORT).show()
                } else {
                    addFiles(paths)
                }
            }
        }.start()
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
        return try {
            var name = ""
            contentResolver.query(uri, arrayOf("_display_name"), null, null, null)?.use { c ->
                if (c.moveToFirst()) name = c.getString(0) ?: ""
            }
            if (name.isEmpty())
                name = uri.lastPathSegment?.substringAfterLast('/') ?: ""
            if (name.isEmpty() || !name.contains('.'))
                name = "media_${System.currentTimeMillis()}.bin"
            name = name.replace(Regex("[/\\\\:*?\"<>|]"), "_")
            var out = File(cacheDir, name)
            var i = 1
            while (out.exists()) {
                val base = name.substringBeforeLast('.'); val ext = name.substringAfterLast('.')
                out = File(cacheDir, "${base}_$i.$ext"); i++
            }
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
        submitList()
        updateCount()
        Toast.makeText(this, "已添加 ${valid.size} 个文件", Toast.LENGTH_SHORT).show()
    }

    private fun removeSelected() {
        val checked = adapter.getChecked()
        files.removeAll(checked)
        adapter.setChecked(emptySet())
        submitList()
        updateCount()
    }

    private fun updateCount() {
        findViewById<TextView>(R.id.lbl_count).text =
            "${getString(R.string.file_list)} · ${files.size} 个文件"
    }

    // ---------------- RecyclerView 数据同步 ----------------
    private fun submitList() {
        val items = files.map { path ->
            FileItem(
                path = path,
                status = rowStatus[path] ?: "",
                progress = rowProgress[path] ?: -1,
                checked = path in adapter.getChecked()
            )
        }
        adapter.submitList(items)
        lblEmpty.visibility = if (files.isEmpty()) View.VISIBLE else View.GONE
    }

    private fun updateItem(path: String) {
        val items = adapter.currentList.map {
            if (it.path == path)
                it.copy(status = rowStatus[path] ?: "", progress = rowProgress[path] ?: -1)
            else it
        }
        adapter.submitList(items)
    }

    private fun adapterCheckedAdd(path: String) {
        // FileAdapter 内部已维护 checked 集合，这里无需额外操作
    }

    private fun adapterCheckedRemove(path: String) {
        // 同上
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
        p["overwrite"] = chkOverwrite.isChecked
        return p
    }

    private fun currentPattern(): String =
        if (spPattern.selectedItemPosition in PATTERNS.indices)
            PATTERNS[spPattern.selectedItemPosition].first
        else edPattern.text.toString().trim().ifEmpty { "{name}" }

    private fun buildOutputPath(src: String, ext: String, index: Int,
                                taken: MutableSet<String>? = null): String {
        val name = File(src).name.substringBeforeLast('.')
        val srcExt = File(src).name.substringAfterLast('.', "")
        val date = SimpleDateFormat("yyyyMMdd", Locale.getDefault()).format(Date())
        val time = SimpleDateFormat("HHmmss", Locale.getDefault()).format(Date())
        val parent = File(src).parentFile?.name ?: ""
        var base = currentPattern()
            .replace("{name}", name).replace("{ext}", srcExt)
            .replace("{date}", date).replace("{time}", time)
            .replace("{index}", String.format("%03d", index))
            .replace("{parent}", parent)
            .replace(Regex("[/\\\\:*?\"<>|]"), "_")
        if (base.isBlank()) base = name
        val dir = outDir.ifEmpty { File(src).parent ?: "." }
        val overwrite = chkOverwrite.isChecked
        var out = File(dir, "$base.$ext")
        var i = 1
        while ((!overwrite && out.exists()) || taken?.contains(out.absolutePath) == true) {
            out = File(dir, "${base}($i).$ext")
            i++
        }
        taken?.add(out.absolutePath)
        return out.absolutePath
    }

    private fun start() {
        if (files.isEmpty()) {
            Toast.makeText(this, R.string.no_files, Toast.LENGTH_SHORT).show()
            return
        }
        val fmt = currentFormat() ?: return
        val params = collectParams()
        val taken = mutableSetOf<String>()
        val jobs = files.mapIndexed { i, src ->
            Job(src, buildOutputPath(src, fmt.ext, i + 1, taken), params.toMap(), kind)
        }
        rowStatus.clear()
        rowProgress.clear()
        files.forEach { rowStatus[it] = "等待中" }
        submitList()
        setBusy(true)
        progress.progress = 0
        lblStatus.text = "开始转换 ${jobs.size} 个文件…"
        Converter.start(jobs, skWorkers.progress + 1)
        prefs.edit().putString("pattern", currentPattern()).apply()
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
        spPreset.isEnabled = !b
        findViewById<MaterialButton>(R.id.btn_presets).isEnabled = !b
        edPattern.isEnabled = !b
        skWorkers.isEnabled = !b
    }

    // ---------------- 预设管理 ----------------
    private fun openPresetManager() {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(12), dp(20), 0)
        }
        val empty = TextView(this).apply {
            text = getString(R.string.preset_empty)
            textSize = 13f
            setPadding(0, dp(8), 0, dp(12))
        }
        val list = android.widget.ListView(this)
        val listAdapter = ArrayAdapter<String>(this, android.R.layout.simple_list_item_1)
        list.adapter = listAdapter
        var selected: String? = null
        list.setOnItemClickListener { _, _, pos, _ ->
            selected = listAdapter.getItem(pos)
        }
        box.addView(empty)
        box.addView(list, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(210)))

        fun refresh() {
            val names = Presets.loadUserPresets().filter { it.kind == kind }.map { it.name }
            listAdapter.clear()
            listAdapter.addAll(names)
            listAdapter.notifyDataSetChanged()
            empty.visibility = if (names.isEmpty()) View.VISIBLE else View.GONE
            list.visibility = if (names.isEmpty()) View.GONE else View.VISIBLE
        }
        refresh()

        val row1 = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(10), 0, 0)
        }
        val row2 = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(4), 0, dp(4))
        }
        fun smallBtn(text: String, onClick: () -> Unit) =
            com.google.android.material.button.MaterialButton(this, null,
                com.google.android.material.R.attr.materialButtonOutlinedStyle).apply {
                this.text = text
                textSize = 12f
                setOnClickListener { onClick() }
            }

        row1.addView(smallBtn(getString(R.string.preset_save)) {
            promptName(getString(R.string.preset_save), "") { name ->
                try {
                    Presets.addUserPreset(Preset(name, kind,
                        currentFormat()?.ext ?: "mp4", makeCurrentPresetParams()))
                    refresh(); refreshPresetSpinner()
                    Toast.makeText(this, "已保存预设「$name」", Toast.LENGTH_SHORT).show()
                } catch (e: IllegalArgumentException) {
                    Toast.makeText(this, e.message ?: "保存失败", Toast.LENGTH_LONG).show()
                }
            }
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        row1.addView(smallBtn(getString(R.string.preset_overwrite)) {
            val name = selected
            if (name == null) { Toast.makeText(this, "先在列表中选中一个用户预设",
                Toast.LENGTH_SHORT).show(); return@smallBtn }
            AlertDialog.Builder(this).setMessage("用当前界面参数重建预设「$name」？")
                .setPositiveButton("重建") { _, _ ->
                    Presets.overwriteUserPreset(name, Preset(name, kind,
                        currentFormat()?.ext ?: "mp4", makeCurrentPresetParams()))
                    refresh(); refreshPresetSpinner()
                    Toast.makeText(this, "已用当前参数重建「$name」", Toast.LENGTH_SHORT).show()
                }
                .setNegativeButton(R.string.cancel, null).show()
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        row1.addView(smallBtn(getString(R.string.preset_rename)) {
            val name = selected
            if (name == null) { Toast.makeText(this, "先在列表中选中一个用户预设",
                Toast.LENGTH_SHORT).show(); return@smallBtn }
            promptName(getString(R.string.preset_rename), name) { newName ->
                try {
                    if (Presets.renameUserPreset(name, newName)) {
                        refresh(); refreshPresetSpinner(); selected = newName
                        Toast.makeText(this, "已重命名为「$newName」", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: IllegalArgumentException) {
                    Toast.makeText(this, e.message ?: "重命名失败", Toast.LENGTH_LONG).show()
                }
            }
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))

        row2.addView(smallBtn(getString(R.string.preset_delete)) {
            val name = selected
            if (name == null) { Toast.makeText(this, "先在列表中选中一个用户预设",
                Toast.LENGTH_SHORT).show(); return@smallBtn }
            AlertDialog.Builder(this).setMessage("删除预设「$name」？")
                .setPositiveButton(R.string.preset_delete) { _, _ ->
                    Presets.deleteUserPreset(name)
                    refresh(); refreshPresetSpinner(); selected = null
                    Toast.makeText(this, "已删除「$name」", Toast.LENGTH_SHORT).show()
                }
                .setNegativeButton(R.string.cancel, null).show()
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        row2.addView(smallBtn(getString(R.string.preset_export)) {
            startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "application/json"
                putExtra(Intent.EXTRA_TITLE, "mediaforge-presets.json")
            }, REQ_EXPORT)
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        row2.addView(smallBtn(getString(R.string.preset_import)) {
            startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "*/*"
            }, REQ_IMPORT)
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))

        box.addView(row1)
        box.addView(row2)

        AlertDialog.Builder(this)
            .setTitle(R.string.preset_manager_title)
            .setView(box)
            .setNegativeButton(R.string.cancel, null as android.content.DialogInterface.OnClickListener?)
            .show()
    }

    private fun promptName(title: String, initial: String, onOk: (String) -> Unit) {
        val ed = android.widget.EditText(this).apply {
            setText(initial)
            setSelection(initial.length)
            setHint("预设名称")
        }
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(8), dp(20), 0)
            addView(ed)
        }
        AlertDialog.Builder(this).setTitle(title).setView(wrap)
            .setPositiveButton("确定") { _, _ -> onOk(ed.text.toString().trim()) }
            .setNegativeButton(R.string.cancel, null as android.content.DialogInterface.OnClickListener?)
            .show()
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    companion object {
        private const val REQ_FILES = 1001
        private const val REQ_OUT_DIR = 1002
        private const val REQ_EXPORT = 1003
        private const val REQ_IMPORT = 1004
    }
}
