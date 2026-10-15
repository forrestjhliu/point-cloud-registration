$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'drawing_helpers.ps1')
$root=$PSScriptRoot
$script:layoutIssues=[Collections.Generic.List[object]]::new()
Add-Type -AssemblyName System.Drawing

function Page($p,$page,$section,$title,$subtitle,$accent) {
    $s=$p.Slides.Add($p.Slides.Count+1,12)
    $s.FollowMasterBackground=0; $s.Background.Fill.ForeColor.RGB=Color $paper
    [void](Box $s 0 0 960 6 $accent)
    [void](Text $s 40 25 620 21 (('{0:00}' -f $page)+'  /  '+$section) 12 $accent $true)
    [void](Text $s 660 25 260 21 '3D VISION  ·  低重叠点云配准' 11 $muted $false 3)
    [void](Text $s 40 62 880 47 $title 29 $ink $true)
    [void](Text $s 40 116 880 40 $subtitle 16 $muted)
    [void](Text $s 873 507 47 18 ($page.ToString()+' / 6') 11 $muted $false 3)
    return $s
}
function Pic($s,$relative,$x,$y,$w,$h) {
    $path=Join-Path $root $relative
    $im=[Drawing.Image]::FromFile($path)
    $ratio=[math]::Min($w/$im.Width,$h/$im.Height)
    $pw=$im.Width*$ratio; $ph=$im.Height*$ratio
    $im.Dispose()
    return $s.Shapes.AddPicture($path,0,-1,[float]($x+($w-$pw)/2),[float]($y+($h-$ph)/2),[float]$pw,[float]$ph)
}
function Takeaway($s,$text,$accent=$blue) {
    [void](Box $s 40 435 880 43 $(if($accent -eq $teal){'E4F1EE'}else{'E8EDF8'}))
    [void](Text $s 55 444 850 28 $text 18 $accent $true)
}
function Legend($s,$x,$y,$color,$text,$w=200) {
    [void](Dot $s ($x+5) ($y+10) 4 $color)
    [void](Text $s ($x+18) $y ($w-18) 24 $text 13 $muted)
}
function SmallMetric($s,$x,$y,$w,$number,$desc,$accent) {
    [void](Text $s $x $y $w 46 $number 33 $accent $true)
    [void](Text $s $x ($y+47) $w 27 $desc 15 $muted)
}
function ExamplePanels($s,$group,$sourceCaption,$referenceCaption) {
    $asset='assets\registration\two_examples\'+$group+'\'
    [void](Text $s 40 171 275 26 '输入：源点云 P' 18 $blue $true)
    [void](Text $s 345 171 275 26 '输入：目标点云 Q' 18 $orange $true)
    [void](Text $s 650 171 270 26 'GT 对齐：P → Q' 18 $ink $true)
    [void](Pic $s ($asset+'input_source.png') 35 199 285 204)
    [void](Pic $s ($asset+'input_reference.png') 340 199 285 204)
    [void](Pic $s ($asset+'gt_common_surface.png') 645 199 285 204)
    [void](Text $s 313 281 28 30 '+' 23 $muted $false 2)
    [void](Seg $s 620 296 643 296 $muted 2 $true)
    [void](Text $s 40 408 280 20 $sourceCaption 12 $muted)
    [void](Text $s 345 408 280 20 $referenceCaption 12 $muted)
    [void](Text $s 650 408 280 20 '绿：GT 辅助标出的共同表面' 12 $teal $true)
}
function SaveDeck($p,$name) {
    foreach($s in $p.Slides){foreach($o in $s.Shapes){
        if($o.HasTextFrame -and $o.TextFrame.HasText){
            $r=$o.TextFrame2.TextRange
            if($r.BoundHeight -gt ($o.Height+4)){
                $script:layoutIssues.Add([pscustomobject]@{deck=$name;slide=$s.SlideIndex;shape=$o.Name;height=$o.Height;bound=$r.BoundHeight;text=$o.TextFrame.TextRange.Text})
            }
        }
    }}
    $p.SaveAs((Join-Path $root ($name+'.pptx')),24)
    $p.SaveAs((Join-Path $root ($name+'.pdf')),32)
    $preview=Join-Path $root ('previews\'+$name)
    [IO.Directory]::CreateDirectory($preview)|Out-Null
    $p.Export($preview,'PNG',1600,900)
    $examples=Join-Path (Split-Path $root -Parent) 'examples'
    [IO.Directory]::CreateDirectory($examples)|Out-Null
    $p.Slides.Item(1).Export((Join-Path $examples '3dmatch_pair_12_to_0.png'),'PNG',3200,1800)
    $p.Slides.Item(3).Export((Join-Path $examples '3dlomatch_pair_30_to_0.png'),'PNG',3200,1800)
    $p.Close()
    Write-Output ('CREATED '+$name+' (6 slides, PPTX + PDF)')
}

$app=New-Object -ComObject PowerPoint.Application
try {
    $p=$app.Presentations.Add(0); $p.PageSetup.SlideWidth=960; $p.PageSetup.SlideHeight=540
    $s=Page $p 1 'MOTIVATION · EXAMPLE 1' '机器人换一个视角，地图就需要重新对齐' '样例 1：同一厨房 · 3DMatch · 元数据 overlap ≈ 61%（共同表面较多）' $blue
    ExamplePanels $s 'high_3dmatch' '片段 12 · 16,341 点 · 本地坐标' '片段 0 · 18,977 点 · 参考坐标'
    Takeaway $s '整个 P 共用一个 R,t；只要求共同表面对齐，无需所有点重合。'
    Footer $s 'RedKitchen 12→0。overlap：GeoTransformer 元数据；绿色：GT 对齐后的 5 cm 邻近标注，非输入或预测。' 'https://github.com/qinzheng93/GeoTransformer#3dmatch'
    Notes $s @'
开场约40秒。先指左、中两图：这就是算法拿到的两块局部地图，蓝色是源P，橙色是目标Q，各有自己的坐标系。机器人换视角以后，看到的表面和坐标都会变化；同一厨房的两份局部地图需要放到一起。再指右图：这是用数据集GT演示正确答案，把整个P刚体移动到Q坐标系，绿色是两份扫描中都观测到的邻近表面。模型实际输出一个R,t，不输出这张图，不创造新表面，也不要求所有点都有对应。
这是真实3DMatch测试pair，7-scenes-redkitchen / source cloud_bin_12 → reference cloud_bin_0，源16341点、目标18977点。点云从PREDATOR预处理ZIP按HTTP Range提取，并验证成员长度与CRC32；GT与两个作者仓库的metadata逐元素一致。第3页保持同一reference0，换成source30，形成教学对照。两组示例不是随机统计样本，也不构成算法性能实验。
百分比统一使用GeoTransformer固定版本e7a135af4c318ff3b8d7f6c963df094d7e4ea540的overlap字段，实际值0.6135477441390187。PREDATOR同一pair的字段为0.4522490812153838，作者字段口径不同；pair身份和GT一致。不要把这些百分比叫遮挡率、图中绿色面积比例或正确匹配比例。
绿色按GT对齐后双向最近邻距离<0.05m逐点标注，仅帮助看见共同表面，不是benchmark overlap的重算，不给模型。输入保持原始XYZ；颜色与点法向明暗只服务渲染。所有面板米制缩放和投影视角相同，输入各自居中；两页Q图片完全相同，两页GT图使用相同显示中心。模型未运行。
课程联系：Lecture2刚体变换；Lecture3对应关系与一致性验证；Lecture4–5点云特征。
来源：https://github.com/prs-eth/OverlapPredator#datasets-and-pretrained-models
配对元数据：https://github.com/qinzheng93/GeoTransformer#3dmatch
完整来源、GT、hash和下载记录：assets/registration/two_examples/examples.json；渲染规则：render_manifest.json。
'@

    $s=Page $p 2 'DATA FORMATION · INPUT · OUTPUT' '一条样本 = 两个局部片段 + 一个 GT 变换' '同一静态场景、尺度一致、有部分重叠；配准模型从两份局部 XYZ 开始。' $blue
    [void](Box $s 40 174 245 103 'FFFFFF' $line)
    [void](Text $s 57 186 211 26 '真实 RGB-D 序列' 19 $blue $true)
    [void](Text $s 57 222 211 45 "深度图 D + 相机内参 K`n每帧的参考位姿" 15 $muted)
    [void](Seg $s 295 225 334 225 $muted 2 $true)
    [void](Box $s 345 174 265 103 'FFFFFF' $line)
    [void](Text $s 362 186 231 26 '每 50 帧融合' 19 $blue $true)
    [void](Text $s 362 222 231 45 "按已有轨迹对齐深度`n得到实际观测到的局部表面" 15 $muted)
    [void](Seg $s 620 225 659 225 $muted 2 $true)
    [void](Box $s 670 174 250 103 'FFFFFF' $line)
    [void](Text $s 687 186 216 26 '一个 fragment' 19 $blue $true)
    [void](Text $s 687 222 216 45 "米制 XYZ 点集`n以该段首帧为局部坐标系" 15 $muted)
    [void](Box $s 40 294 510 123 'FFFFFF' $line)
    [void](Text $s 58 307 474 26 '模型输入：配对列表中的两个片段' 18 $blue $true)
    [void](Text $s 58 343 474 26 'P：片段 12，16,341 × 3' 20 $ink)
    [void](Text $s 58 377 474 26 'Q：片段 0，18,977 × 3' 20 $ink)
    [void](Box $s 580 294 340 123 'FFFFFF' $line)
    [void](Text $s 598 307 304 26 'GT 标签：模型看不到' 18 $orange $true)
    [void](Text $s 598 343 304 28 'T*：4 × 4 刚体变换' 21 $ink $true)
    [void](Text $s 598 380 304 23 '从 P 坐标映射到 Q 坐标' 15 $muted)
    Takeaway $s '模型：两份 XYZ → R∈SO(3), t∈ℝ³；对整个 P 执行 p↦Rp+t。'
    Footer $s '上方是数据集离线准备。点集每行是一个 XYZ；P、Q 的行号不表示对应。参考位姿和 GT 不作为测试输入。' 'https://github.com/andyzeng/3dmatch-toolbox/tree/master/depth-fusion'
    Notes $s @'
约60秒。按帧→片段→样本三个层次讲。最原始的是人在室内移动RGB-D相机拍下的序列，包含颜色、深度、内参和已有参考位姿。一个有效深度像素(u,v,d)可按p=d K^-1[u,v,1]反投影为三维点。原始深度文件以毫米保存，计算时转换成米。参考位姿由已有重建提供，不是本项目预测的输入。
官方fuseSceneFragments.m每50帧融合一次；demo.cu将该段第一帧选为局部坐标基准，利用inv(T_world_base)T_world_frame把其余帧变换进来，再通过TSDF融合并提取局部表面点。fragment的世界位姿保存该首帧camera-to-world矩阵。每个片段仍只包含那段时间真正观测到的表面，不是完整房间或物体。它也不是一张深度图，也不是原论文另一个局部patch分类任务里的小立方体。
我们不用重新做这些准备工作，直接读作者发布的预处理点云。一个配准样本由P、Q和正确答案T*组成，但只有P和Q输入模型。以第1页为例，P为片段12的16341×3数组，Q为片段0的18977×3数组。点数不同、行顺序任意，没有逐行一一对应关系。颜色只是可视化，不是当前setting的输入特征。
输出R属于SO(3)，满足正交且行列式为1；t是3维米制平移。对每个源点执行Rp+t进入目标坐标，所有点共用同一变换。GT是4×4齐次矩阵，包含旋转和平移，不是每点一个类别。已知尺度，不需要估计缩放；已知来自同一静态场景并存在重叠，不做跨场景检索、是否重叠的二分类、动态物体或非刚体配准。
上方轨迹用于数据集离线构建；下方模型测试时看不到该轨迹、初始相对位姿、GT对应或重叠标签。
https://github.com/andyzeng/3dmatch-toolbox/blob/master/depth-fusion/fuseSceneFragments.m
https://github.com/andyzeng/3dmatch-toolbox/blob/master/depth-fusion/demo.cu
https://github.com/qinzheng93/GeoTransformer
'@

    $s=Page $p 3 'WHY IT IS HARD · EXAMPLE 2' '只换一个片段，共同表面就大幅减少' '样例 2：同一厨房、同一参考 Q · 3DLoMatch · 元数据 overlap ≈ 20%' $blue
    ExamplePanels $s 'low_3dlomatch' '片段 30 · 11,054 点 · 本地坐标' '仍是片段 0 · 与第 1 页完全相同'
    Takeaway $s '只有共同表面能提供真实对应；大片非重叠区域不该强行匹配。'
    Footer $s 'RedKitchen 30→0。overlap：GeoTransformer 元数据；绿色：GT 对齐后的 5 cm 邻近标注，非输入或预测。' 'https://github.com/qinzheng93/GeoTransformer#3dmatch'
    Notes $s @'
约40秒。先指中间：目标Q和第1页完全一样，连图片的视角和大小都没变；现在只把源片段换成30。再看右边，用GT把两份点云放回同一坐标系后，绿色共同表面明显减少，蓝色和橙色各有大块独有区域。那些区域根本没有真实对应，不能期待把所有点重合。真正的问题是：输入没有绿色标注，要从局部XYZ里找到少量可靠对应，估计一个对整个源点云适用的R,t。
这是3DLoMatch测试pair，7-scenes-redkitchen / source cloud_bin_30 → reference cloud_bin_0，源11054点、目标18977点，不在3DMatch配对列表中。GeoTransformer元数据overlap=0.1993072286242296；PREDATOR为0.2022。固定作者列表，不按另一个字段重新筛选。右图是GT对齐和解释性标注，既不是作者方法预测，也不是本项目结果。
两页都用同一相机方向、米制缩放、GT图中心和5cm邻近标注规则；Q图逐像素相同。绿色只表达GT下的邻近表面，不等于metadata overlap计算口径，不用于输入或候选筛选。完整数组、来源和GT方向见assets/registration/two_examples/examples.json。
这是两种典型情形的教学对照，不表示高重叠必定容易、低重叠必定失败，也没有在实验上隔离旋转角度等其他因素。低重叠由视野变化和遮挡共同造成；重复墙面、局部几何相似还会造成对应歧义。错误匹配率取决于特征和采样，不能用1-overlap替代。
启发：正确对应还必须共同支持同一个刚体变换，因此可以研究几何一致性筛选。不要提前承诺该规则一定改善。
https://github.com/prs-eth/OverlapPredator#datasets-and-pretrained-models
https://github.com/qinzheng93/GeoTransformer#3dmatch
'@

    $s=Page $p 4 'DATASET · DISTRIBUTION' '同一批场景，组成两份难度不同的测试列表' '1,623 和 1,781 数的是“片段对”；一个片段可以参与多个配准样本。' $blue
    [void](Box $s 40 174 265 79 'FFFFFF' $line)
    [void](Text $s 57 184 231 28 '同一批 8 个测试场景' 19 $blue $true)
    [void](Text $s 57 221 231 22 '厨房、家庭、酒店、学习室、实验室' 12.5 $muted)
    [void](Seg $s 316 212 349 193 $muted 1.7 $true)
    [void](Seg $s 316 215 349 238 $muted 1.7 $true)
    [void](Box $s 360 170 560 42 'E8EDF8')
    [void](Text $s 376 179 528 27 '3DMatch：1,623 对 · 标称重叠 >30%' 19 $blue $true)
    [void](Box $s 360 223 560 42 'E4F1EE')
    [void](Text $s 376 232 528 27 '3DLoMatch：1,781 对 · 标称 10%–30%' 19 $teal $true)
    [void](Text $s 40 278 470 26 '实测配对分布：各场景不均衡' 17 $ink $true)
    [void](Text $s 584 278 336 26 '刚才的两例，就是两条配对记录' 17 $blue $true)
    $sceneRows=@(@('RedKitchen',506,525),@('Home AT',156,289),@('Home MD',208,230),@('Hotel UC',226,218),@('Hotel UMD 1',104,158),@('Hotel UMD 3',54,49),@('MIT Studyroom',292,240),@('MIT Lab',77,72))
    for($i=0;$i -lt $sceneRows.Count;$i++){
        $yy=312+$i*14.5
        [void](Text $s 40 $yy 135 17 $sceneRows[$i][0] 10.5 $muted)
        [void](Box $s 178 ($yy+1) (210*$sceneRows[$i][1]/525.0) 4.2 $blue)
        [void](Box $s 178 ($yy+7) (210*$sceneRows[$i][2]/525.0) 4.2 $teal)
        [void](Text $s 405 $yy 110 17 ($sceneRows[$i][1].ToString()+' / '+$sceneRows[$i][2]) 10.5 $muted)
    }
    [void](Text $s 584 317 336 29 '片段 12 → 片段 0：样例 1' 18 $blue $true)
    [void](Text $s 584 357 336 29 '片段 30 → 片段 0：样例 2' 18 $teal $true)
    [void](Text $s 584 397 336 25 '3DLoMatch 沿用相同来源的扫描片段' 15 $muted)
    Takeaway $s '片段可重复出现；训练与验证关注场景隔离，测试保留作者配对列表。'
    Footer $s '蓝 / 绿为 Match / LoMatch。当前列表共享 100 对；标称区间与不同发布版 overlap 字段不能混用重筛。' 'https://github.com/prs-eth/OverlapPredator'
    Notes $s @'
约60秒。3DMatch这个名字既是原论文的描述子方法，也指其后使用的数据和benchmark。我们用的是场景fragment配准任务，不是原论文30000个局部patch的二分类任务。3DMatch汇集真实室内RGB-D数据；3DLoMatch由PREDATOR工作在相同来源的扫描上构造低重叠配对评测，不是另一种传感器，不是不同的一批机器人，也不是我们人工裁掉点云制造的遮挡。
解释1,623对与1,781对：一行是同场景的两个片段路径和一个相对GT，一个片段可反复配给多个其他片段。刚才ref0分别配src12和src30就是两个不同样本。两套测试都覆盖厨房、家庭、酒店、学习室和实验室这8个独立测试场景。它们是有重叠的静态室内片段对，不代表任意两张扫描，更不代表所有机器人场景的分布。
实测8测试场景中Match1623对、LoMatch1781对，两列表共享100对，并不互斥；类别为厨房、家庭、酒店、学习室和实验室，配对数明显不均衡，因此主指标按官方场景均值。标称重叠门槛分别>30%和10%–30%，不是物理遮挡率；当前不同仓库overlap字段不同，不重新筛掉边界外pair。
overlap要在正确对齐后才能定义：按给定采样与距离阈值，看一份点集有多少点在另一份点集中存在邻近表面。它一般不是图像交并比，也不保证两个方向比例相同。图上绿色是我们的5cm可视化辅助，与作者metadata overlap并非同一计算口径。实际错误匹配率还取决于模型和采样。
原始文献54训练/8测试；后续论文46/8/8。当前GeoTransformer元数据train20642对、75序列名，val1331对、8序列名，按原场景档案名称映射为48和6。train/val共享apt2-kitchen的75对和19个fragment，test与二者无路径交叉。本项目先冻结特征，若训练新模块需从train剔除共享场景；已有权重的历史不能由删除manifest改变。详见上一版dataset_audit_zh.txt和research/registration_audit.json。
不要把pair随机打散就宣称训练测试独立，因为同一片段甚至完全相同配对可能进入两边。场景不均衡也意味着全体pair直接平均会更偏向RedKitchen，官方RR采用场景等权。
PREDATOR预处理压缩包经HEAD约936MB；解压大小未测。本次两组教学样例仅按HTTP Range获取ZIP目录与3个片段，共1370160字节，没有下载完整数据包。
https://github.com/prs-eth/OverlapPredator
https://github.com/qinzheng93/GeoTransformer
'@

    $s=Page $p 5 'GROUND TRUTH · TARGET' '构建者有参考轨迹，模型只看两份 XYZ' '把 P 先映射到世界，再映射回 Q；两次变换合成这条样本的正确答案。' $blue
    [void](Box $s 40 176 205 83 'FFFFFF' $line)
    [void](Text $s 58 188 169 29 'P 的局部坐标' 21 $blue $true)
    [void](Text $s 58 225 169 23 '源片段' 15 $muted)
    [void](Text $s 254 177 109 24 'T_W←P' 17 $blue $true 2)
    [void](Seg $s 256 221 363 221 $blue 2 $true)
    [void](Box $s 375 176 205 83 'FFFFFF' $line)
    [void](Text $s 393 188 169 29 '世界坐标' 21 $ink $true)
    [void](Text $s 393 225 169 23 '已有场景重建' 15 $muted)
    [void](Text $s 589 177 117 24 '(T_W←Q)⁻¹' 16 $blue $true 2)
    [void](Seg $s 591 221 698 221 $blue 2 $true)
    [void](Box $s 710 176 210 83 'FFFFFF' $line)
    [void](Text $s 728 188 174 29 'Q 的局部坐标' 21 $orange $true)
    [void](Text $s 728 225 174 23 '目标片段' 15 $muted)
    [void](Text $s 40 278 880 35 'T* = (T_W←Q)⁻¹ T_W←P     ·     4×4，源 → 目标' 24 $ink $true 2)
    [void](Seg $s 40 326 920 326 $line 1)
    [void](Text $s 40 341 460 26 '每条有效测试样本：成功还是失败？' 17 $blue $true)
    [void](Text $s 40 377 460 31 '预测与 GT 的官方变换误差 <0.2 m' 20 $ink $true)
    [void](Text $s 558 341 362 26 'Registration Recall 怎么汇总？' 17 $blue $true)
    [void](Text $s 558 377 362 45 "排除直接相邻片段后，逐场景计算`n成功比例，再对 8 个场景等权平均" 16 $ink)
    Takeaway $s 'GT 用来判定 R,t 是否正确；没有要求两片点云的所有表面都重合。'
    Footer $s 'RR 有效对：Match 1,279 / LoMatch 1,726。误差按官方信息矩阵协议计算；GT 来自重建参考位姿。' 'https://github.com/qinzheng93/GeoTransformer/blob/e7a135af4c318ff3b8d7f6c963df094d7e4ea540/geotransformer/datasets/registration/threedmatch/utils.py'
    Notes $s @'
约60秒。先讲数据集构建者和被评测算法拥有不同信息：构建者可用完整RGB-D序列、已有参考轨迹和离线重建，算法仅得到两个fragment的XYZ。GT不是模型泄露出来的答案，而是单独保存的评价标签。
顺着三个坐标框讲：T_WP把源片段的局部坐标送到世界；inv(T_WQ)再把世界坐标送回目标片段的坐标。因此T*=inv(T_WQ)T_WP。所有T都是4×4齐次矩阵，上左3×3为R，右上3×1为t，最后一行为0,0,0,1。官方GT代码读取各片段首帧已有位姿，保存fragment2→fragment1的变换，与本项目src→ref相同。该参考来自重建，并非绝对无噪声的动捕测量。
模型输出一个预测T，评价端拿GT比较。官方标准RR使用gt.info里由参考对应几何计算的信息矩阵，对位姿误差做归一化二次型，以其平方根（重对齐RMSE的近似）<0.2m判成功。实现代码比较平方误差<0.2²。这不是t的范数、R/t元素RMSE或普通最近邻Chamfer，也不是所有点要在20cm内逐个重合。
关键计数：作者RR协议排除直接相邻的fragment（frag_id1>frag_id0+1），然后在每个场景内求成功比例，再把8个场景等权平均。第4页1623/1781是加载配对列表的规模，不可直接用它们做全局RR分母。固定metadata实测有效对为Match1279、LoMatch1726。两教学样本12→0和30→0均为非相邻片段，均在有效列表中。各场景计数与证据见research/rr_protocol_audit.json。
不变的是评价目标：Match与LoMatch分别报告官方RR和耗时。如果另报RRE/RTE，需注明作者实现仅对成功配准样本统计这些量。GT、参考对应和overlap标记都不用于测试时筛选。
https://github.com/andyzeng/3dmatch-toolbox/blob/master/evaluation/geometric-registration/getGtInfoLog.m
https://github.com/qinzheng93/GeoTransformer/blob/e7a135af4c318ff3b8d7f6c963df094d7e4ea540/experiments/geotransformer.3dmatch.stage4.gse.k3.max.oacl.stage2.sinkhorn/eval.py
'@

    $s=Page $p 6 'HYPOTHESIS · NEXT STEP' '固定特征与求解器，检验哪种对应更可靠' '假设：把更多预算用于几何一致的对应，能提高低重叠配准成功率。' $blue
    Label $s 40 177 223 '冻结点云特征 → 候选对应' $blue
    [void](Seg $s 275 191 310 191 $muted 2 $true)
    Label $s 323 177 275 '只改变：对应筛选规则' $blue
    [void](Seg $s 610 191 645 191 $muted 2 $true)
    Label $s 658 177 262 '同一 RANSAC → R, t' $blue
    [void](Text $s 40 244 424 28 '几何启发' 19 $blue $true)
    [void](Text $s 40 292 424 48 '‖pᵢ − pⱼ‖ ≈ ‖qᵢ − qⱼ‖' 27 $ink $true)
    [void](Text $s 40 355 424 62 "刚体变换保持点间距离`n由多个对应之间的一致性辅助筛选" 17 $muted)
    [void](Seg $s 485 245 485 409 $line 1)
    [void](Text $s 518 244 402 28 '最小对照' 19 $blue $true)
    [void](Text $s 518 289 402 119 "同一候选池，按两种评分各取 K 对`n同 RANSAC 预算、同测试列表`n主看 LoMatch RR，也检查 Match`n先复现，再按失败类型确定规则" 18 $ink)
    Takeaway $s '预期产出：一个可复现基线 + 一项受控对照 + 低重叠失败案例分析。'
    Footer $s '拟以 PREDATOR 特征 + RANSAC 起步；几何一致性是已有思想，效果与具体改进需要实验检验。' 'https://github.com/prs-eth/OverlapPredator'
    Notes $s @'
收束约40秒。前五页已把输入、输出、困难、数据和目标闭合；现在只提出可验证的课程实验，不承诺一个尚未实现的新方法。先复现PREDATOR特征与RANSAC，然后缓存固定的候选对应池。在受控对照里，原匹配评分与几何一致性评分各自排序后取Top-K进入同一个RANSAC；K在开发集预先固定。池不足K时双方统一取min(K,池大小)，不重复补点。避免用硬阈值剔除导致两边对应预算不同。论文原始评测另行复现，不把我们这个受控选择协议冒称论文默认设置。规则和阈值在开发集选，测试只评价。
点间距离在刚体变换下保持不变，允许用多个对应共同支持一个几何解释。但重复结构也可能错误地保持局部距离，所以成功与否需实验。GeoTransformer等已利用几何关系，不能把加入几何一致性笼统当作原创贡献。课程贡献可以是可复现的受控比较与失败分析，明确什么时候有用、什么时候无用。
https://github.com/prs-eth/OverlapPredator
课程联系：Lecture2 R/t，Lecture3匹配与一致性验证，Lecture4–5局部点云特征。
'@
    SaveDeck $p 'low_overlap_registration_6slides'
} finally {
    $app.Quit()
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)
}
ConvertTo-Json -InputObject @($script:layoutIssues.ToArray()) -Depth 6 | Set-Content -LiteralPath (Join-Path $root 'layout_check.json') -Encoding UTF8
Write-Output ('LAYOUT_OVERFLOWS '+$script:layoutIssues.Count)
& (Join-Path (Split-Path $PSScriptRoot -Parent) 'sync_proposal.ps1')
