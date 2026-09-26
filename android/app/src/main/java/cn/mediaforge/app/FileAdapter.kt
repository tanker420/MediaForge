package cn.mediaforge.app

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.CheckBox
import android.widget.ImageView
import android.widget.ProgressBar
import android.widget.TextView
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.card.MaterialCardView
import java.io.File

/** 文件条目数据。 */
data class FileItem(
    val path: String,
    val status: String = "",
    val progress: Int = -1,   // -1 表示无进度
    val checked: Boolean = false,
)

/**
 * 文件列表 RecyclerView 适配器（Material3 风格）。
 * 每个条目：复选框 + 类型图标 + 文件名 + 状态/进度 + 可点击选中。
 */
class FileAdapter(
    private val onToggle: (path: String, checked: Boolean) -> Unit,
    private val onClick: (path: String) -> Unit,
) : ListAdapter<FileItem, FileAdapter.VH>(DIFF) {

    private val _checked = mutableSetOf<String>()

    fun setChecked(paths: Set<String>) {
        _checked.clear(); _checked.addAll(paths)
        notifyItemRangeChanged(0, currentList.size, PAYLOAD_CHECK)
    }

    fun getChecked(): Set<String> = _checked.toSet()

    fun updateItem(path: String, status: String? = null, progress: Int? = null) {
        val idx = currentList.indexOfFirst { it.path == path }
        if (idx < 0) return
        notifyItemChanged(idx, PAYLOAD_STATUS)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_file, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        holder.bind(getItem(position))
    }

    override fun onBindViewHolder(holder: VH, position: Int, payloads: MutableList<Any>) {
        if (payloads.isEmpty()) {
            onBindViewHolder(holder, position); return
        }
        val item = getItem(position)
        if (payloads.contains(PAYLOAD_CHECK)) holder.updateCheck(item)
        if (payloads.contains(PAYLOAD_STATUS)) holder.updateStatus(item)
    }

    inner class VH(v: View) : RecyclerView.ViewHolder(v) {
        private val card = v.findViewById<MaterialCardView>(R.id.card)
        private val icon = v.findViewById<ImageView>(R.id.row_icon)
        private val name = v.findViewById<TextView>(R.id.row_name)
        private val meta = v.findViewById<TextView>(R.id.row_meta)
        private val status = v.findViewById<TextView>(R.id.row_status)
        private val bar = v.findViewById<ProgressBar>(R.id.row_progress)
        private val check = v.findViewById<CheckBox>(R.id.row_check)

        fun bind(item: FileItem) {
            val f = File(item.path)
            name.text = f.name
            meta.text = "${humanSize(f.length())}  ·  ${f.extension.uppercase()}"
            icon.setImageResource(kindIcon(item.path))

            updateCheck(item)
            updateStatus(item)

            card.setOnClickListener { onClick(item.path) }
            card.setOnLongClickListener {
                check.performClick(); true
            }
            check.setOnCheckedChangeListener { _, isChecked ->
                onToggle(item.path, isChecked)
            }
        }

        fun updateCheck(item: FileItem) {
            val isChecked = item.path in _checked
            check.setOnCheckedChangeListener(null)
            check.isChecked = isChecked
            check.setOnCheckedChangeListener { _, checked ->
                onToggle(item.path, checked)
            }
            card.isChecked = isChecked
        }

        fun updateStatus(item: FileItem) {
            status.text = item.status
            when {
                item.progress >= 0 -> {
                    bar.visibility = View.VISIBLE
                    bar.progress = item.progress
                    status.visibility = View.VISIBLE
                }
                item.status.isNotEmpty() -> {
                    bar.visibility = View.GONE
                    status.visibility = View.VISIBLE
                }
                else -> {
                    bar.visibility = View.GONE
                    status.visibility = View.GONE
                }
            }
        }
    }

    private fun kindIcon(path: String): Int = when (Formats.detectKind(path)) {
        Formats.VIDEO -> R.drawable.ic_video
        Formats.AUDIO -> R.drawable.ic_audio
        else -> R.drawable.ic_image
    }

    private fun humanSize(n: Long): String = when {
        n >= 1_000_000_000 -> "%.2f GB".format(n / 1_000_000_000.0)
        n >= 1_000_000 -> "%.1f MB".format(n / 1_000_000.0)
        n >= 1_000 -> "%.0f KB".format(n / 1_000.0)
        else -> "$n B"
    }

    companion object {
        private const val PAYLOAD_CHECK = "check"
        private const val PAYLOAD_STATUS = "status"

        val DIFF = object : DiffUtil.ItemCallback<FileItem>() {
            override fun areItemsTheSame(a: FileItem, b: FileItem) = a.path == b.path
            override fun areContentsTheSame(a: FileItem, b: FileItem) = a == b
        }
    }
}
