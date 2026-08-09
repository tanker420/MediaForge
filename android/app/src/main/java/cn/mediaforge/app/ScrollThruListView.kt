package cn.mediaforge.app

import android.content.Context
import android.util.AttributeSet
import android.view.MotionEvent
import android.widget.ListView

/** 高度按内容自适应（由 MainActivity 测量后设置），自身不消费滚动手势，
 *  整页滚动统一交给外层 ScrollView——修复列表区域上滑无响应的问题。 */
class ScrollThruListView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : ListView(context, attrs) {
    override fun onTouchEvent(ev: MotionEvent): Boolean = false
    override fun onInterceptTouchEvent(ev: MotionEvent): Boolean = false
}
