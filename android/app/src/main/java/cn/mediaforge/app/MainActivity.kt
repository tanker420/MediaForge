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
import android.widget.BaseAdapter
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ListView
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
import com.google.android.material.button.MaterialButton
import com.google.android.material.color.MaterialColors
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
    private lateinit var spPreset: Spinner
    private lateinit var edPattern: EditText
    private lateinit var skWorkers: SeekBar
    private lateinit var lblWorkers: TextView
    private lateinit var form: ParamForm
    private lateinit var edOutdir: EditText
    private lateinit var progress: ProgressBar
    private lateinit var lblStatus: TextView
    private lateinit var btnStart: MaterialButton
    private lateinit var btnCancel: MaterialButton
    private lateinit var lblVcodec: TextView
    private lateinit var lblAcodec: TextView
    private lateinit var lblEmpty: TextView
    private var presetPool: List<Preset> = emptyList()

    private val PATTERNS = listOf("{name}" to "原文件名", "{name}_converted" to "原文件名_converted",
        "{name}_{date}" to "原文件名_日期", "{parent}_{name}" to "上级目录_文件名")

    override fun onCreate(savedInstanceState: Bundle?) {
        prefs = getSharedPreferences("mediaforge", MODE_PRIVATE)
        applyThemeFromPrefs()
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        setContentView(R.layout.activity_main)

        // 状态栏 / 导航栏内边距：头部与底栏各自吃掉对应 inset
        val header = findViewById<View>(R.id.app_header)
        val headerTop = header.paddingTop
        ViewCompat.setOnApplyWindowInsetsListener(header) { v, insets ->
            v.setPadding(v.paddingLeft,
                headerTop + insets.getInsets(WindowInsetsCompat.Type.statusBars()).top,
                v.paddingRight, v.paddingBottom)
            insets
        }
        val footer = findViewById<View>(R.id.footer_bar)
        val footerBottom = footer.paddingBottom
        ViewCompat.setOnApplyWindowInsetsListener(footer) { v, insets ->
            v.setPadding(v.paddingLeft, v.paddingTop, v.paddingRight,
                footerBottom + insets.getInsets(WindowInsetsCompat.Type.navigationBars()).bottom)
            insets
        }

        findViewById<View>(R.id.btn_theme).setOnClickListener { toggleTheme() }
        refreshThemeButton()

        // 选项卡颜色从 Material 主题令牌取，深浅色自动跟随
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

        adapter = FileAdapter()
        fileList.adapter = adapter

        findViewById<MaterialButton>(R.id.btn_add).setOnClickListener { pickFiles() }
        findViewById<MaterialButton>(R.id.btn_remove).setOnClickListener { removeSelected() }
        findViewById<MaterialButton>(R.id.btn_clear).setOnClickListener {
            files.clear(); checked.clear(); rowStatus.clear(); refreshFileList(); updateCount()
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

        // 命名规则：内置默认选项 + 自定义…
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

        // 并行任务：滑块 1~8（防呆：SeekBar 天然限定范围）
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

        outDir = prefs.getString("out_dir", "") ?: ""
        edOutdir.setText(outDir)

        ensureStorage()
        applyKind(Formats.VIDEO)
        refreshFileList()

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
        applyThemeFromPrefs()   // 触发重建，立即生效
    }

    private fun refreshThemeButton() {
        findViewById<MaterialButton>(R.id.btn_theme).text =
            if (prefs.getBoolean("ui_dark", false))
                getString(R.string.theme_toggle_night) else getString(R.string.theme_toggle)
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
        refreshPresetSpinner()
        rebuildCodecsAndForm()
        adapter.notifyDataSetChanged()
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

    /** 套用预设：先切格式/编码器（异步重建表单），再回填参数。 */
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

    /** 当前界面参数汇总成可保存的预设参数（含格式与编码器）。 */
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

    private fun uriToPath(uri: Uri): String? {
        try {
            contentResolver.query(uri, arrayOf("_data"), null, null, null)?.use { c ->
                if (c.moveToFirst()) {
                    val v = c.getString(0)
                    if (!v.isNullOrEmpty() && File(v).exists()) return v
                }
            }
        } catch (e: Exception) { /* fallthrough 到拷贝 */ }
        // 无法直接取路径：拷贝到缓存目录。
        // 关键：必须保留原文件名（含扩展名），否则 addFiles 的
        // 扩展名白名单过滤会把文件全部丢弃（“上传后无法识别”的根因）。
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
        refreshFileList()
        updateCount()
        Toast.makeText(this, "已添加 ${valid.size} 个文件", Toast.LENGTH_SHORT).show()
    }

    private fun removeSelected() {
        files.removeAll(checked)
        checked.clear()
        refreshFileList()
        updateCount()
    }

    private fun updateCount() {
        findViewById<TextView>(R.id.lbl_count).text =
            "${getString(R.string.file_list)} · ${files.size} 个文件"
    }

    /** 列表数据变化后：切换空状态提示，并把列表高度重测为内容高度
     *  （列表嵌在整体 ScrollView 内，自身不滚动）。 */
    private fun refreshFileList() {
        adapter.notifyDataSetChanged()
        lblEmpty.visibility = if (files.isEmpty()) View.VISIBLE else View.GONE
        fileList.post {
            var h = fileList.paddingTop + fileList.paddingBottom
            val a = fileList.adapter ?: return@post
            for (i in 0 until a.count) {
                val itemView = a.getView(i, null, fileList)
                itemView.measure(
                    View.MeasureSpec.makeMeasureSpec(fileList.width, View.MeasureSpec.EXACTLY),
                    View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED))
                h += itemView.measuredHeight
            }
            h += fileList.dividerHeight * maxOf(0, a.count - 1)
            val lp = fileList.layoutParams
            if (lp.height != h) { lp.height = h; fileList.layoutParams = lp }
        }
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

    private fun currentPattern(): String =
        if (spPattern.selectedItemPosition in PATTERNS.indices)
            PATTERNS[spPattern.selectedItemPosition].first
        else edPattern.text.toString().trim().ifEmpty { "{name}" }

    private fun buildOutputPath(src: String, ext: String, index: Int): String {
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
        val jobs = files.mapIndexed { i, src ->
            Job(src, buildOutputPath(src, fmt.ext, i + 1), params.toMap(), kind)
        }
        rowStatus.clear()
        files.forEach { rowStatus[it] = "等待中" }
        adapter.notifyDataSetChanged()
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
        val list = ListView(this)
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
        val ed = EditText(this).apply {
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
        private const val REQ_EXPORT = 1003
        private const val REQ_IMPORT = 1004
    }
}
