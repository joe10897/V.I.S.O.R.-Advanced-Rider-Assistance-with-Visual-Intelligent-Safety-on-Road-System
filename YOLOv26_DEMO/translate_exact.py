def translate_exact_html():
    html_path = r"C:\Users\USER\Desktop\motorcycle_assist\YOLOv26_DEMO\presentation.html"
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Mappings of exact HTML blocks
    blocks = {
        # --- Slide 2 ---
        """                    <p style="font-size: 18px; line-height: 1.7; margin-bottom: 20px;">
                        在高密度混合交通環境中，機車騎士是<strong>最脆弱的弱勢道路使用者(VRU)</strong>。車流交織和視野死角直接加劇了傷亡風險。
                    </p>""": """                    <p style="font-size: 18px; line-height: 1.7; margin-bottom: 20px;">
                        In high-density mixed traffic, motorcycle riders are the <strong>Vulnerable Road Users (VRUs)</strong>. Traffic conflicts and blind spots directly amplify injury and fatality risks.
                    </p>""",
        
        """                        <li style="margin-bottom: 12px; font-size: 15px;"><strong>不對等防護：</strong>
                            機車不具備剛性車體結構保護，死傷率高達四輪乘用車的 <strong>28 倍</strong>。</li>""": """                        <li style="margin-bottom: 12px; font-size: 15px;"><strong>Asymmetrical Protection:</strong>
                            Motorcycles lack rigid protective structural frames, causing a fatality rate up to <strong>28 times</strong> higher than passenger cars.</li>""",
                            
        """                        <li style="margin-bottom: 12px; font-size: 15px;"><strong>環境感知盲點：</strong>
                            騎士需在秒級動態路況中，在不當變換車道、後方逼車或前車驟停中迅速作出反應。</li>""": """                        <li style="margin-bottom: 12px; font-size: 15px;"><strong>Environmental Blind Spots:</strong>
                            Riders must react in split-seconds to improper lane changes, tailgating, or sudden braking.</li>""",
                            
        """                        <li style="margin-bottom: 12px; font-size: 15px;"><strong>缺乏專屬方案：</strong>
                            市售高階 ADAS 與雷達多為汽車設計，體積龐大且昂貴，無法在平價機車上普及。</li>""": """                        <li style="margin-bottom: 12px; font-size: 15px;"><strong>No Dedicated Solutions:</strong>
                            Commercial ADAS and radars are designed for cars, being bulky and expensive, which prevents popularization on budget bikes.</li>""",
                            
        """                    <h3 style="font-size: 18px; color: var(--brand-teal); margin-bottom: 10px;">台灣高密度道路事故威脅</h3>""": """                    <h3 style="font-size: 18px; color: var(--brand-teal); margin-bottom: 10px;">High-Density Roadway Conflicts</h3>""",
        
        """                    <p style="font-size: 14px; line-height: 1.6; color: var(--text-secondary);">
                        車道混亂、超車頻繁，需要毫秒級的 360 度動態偵測警報系統，防止機車在視野盲點發生碰撞自摔。
                    </p>""": """                    <p style="font-size: 14px; line-height: 1.6; color: var(--text-secondary);">
                        Chaotic lanes and frequent overtaking require millisecond-level 360-degree dynamic detection to prevent blind-spot collisions.
                    </p>""",
                    
        """                    <p style="font-size: 12px; color: var(--text-muted); margin-top: 15px; font-style: italic;">
                        (點擊卡片可模擬主動警告音效)
                    </p>""": """                    <p style="font-size: 12px; color: var(--text-muted); margin-top: 15px; font-style: italic;">
                        (Click cards to simulate active warning sounds)
                    </p>""",

        # --- Slide 3 ---
        """                    <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 15px; font-style: italic;">
                        在雷達區域移動滑鼠/手指以模擬威脅車輛
                    </p>""": """                    <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 15px; font-style: italic;">
                        Move cursor/finger on the radar area to simulate threat vehicles.
                    </p>""",
                    
        """                        <h3 style="font-size: 20px; font-weight: 700; color: var(--brand-navy); margin-bottom: 15px;">
                            V.I.S.O.R. 280° 廣角感知覆蓋</h3>""": """                        <h3 style="font-size: 20px; font-weight: 700; color: var(--brand-navy); margin-bottom: 15px;">
                            V.I.S.O.R. 280° Wide-Angle Perception</h3>""",
                            
        """                        <p style="font-size: 15px; line-height: 1.7; margin-bottom: 25px;">
                            本專案設計以 <strong>低成本、純視覺、全方位保護</strong> 為導向，實現多重主動安全機制：
                        </p>""": """                        <p style="font-size: 15px; line-height: 1.7; margin-bottom: 25px;">
                            This project designs a low-cost, pure-vision, all-around active safety shield:
                        </p>""",
                        
        """                            <li style="margin-bottom: 15px; font-size: 14.5px;"><strong>雙向無死角監視：</strong>
                                前置 120° 與後置 160° 雙廣角鏡頭，完美防禦左右盲區逼車。</li>""": """                            <li style="margin-bottom: 15px; font-size: 14.5px;"><strong>Dual-Direction Monitoring:</strong>
                                Front 120° and rear 160° lenses eliminate lateral and rear blind spots.</li>""",
                                
        """                            <li style="margin-bottom: 15px; font-size: 14.5px;"><strong>動態威脅區間劃分：</strong>
                                演算法即時判別侵入物體落點，自動切換前向防追撞與後向逼車警報。</li>""": """                            <li style="margin-bottom: 15px; font-size: 14.5px;"><strong>Dynamic Threat Zoning:</strong>
                                Instantly identifies threat entry points, switching automatically between front and rear alarms.</li>""",
                                
        """                            <li style="margin-bottom: 0; font-size: 14.5px;"><strong>聲音空間疊加警示：</strong>
                                結合無線安全帽耳機，當威脅在左後方時，音效會指向左耳，提升騎士本能直覺。</li>""": """                            <li style="margin-bottom: 0; font-size: 14.5px;"><strong>3D Spatialized Audio:</strong>
                                Helmet audio points to the direction of threats (e.g. left rear), enabling intuitive reflexes.</li>""",

        # --- Slide 5 ---
        """                    <h3 style="font-size: 18px; color: var(--brand-teal); margin-bottom: 12px;">視覺神經網路在邊緣端的革新</h3>""": """                    <h3 style="font-size: 18px; color: var(--brand-teal); margin-bottom: 12px;">Edge-Based Vision Neural Network Evolution</h3>""",
        
        """                    <p style="font-size: 14.5px; line-height: 1.7; margin-bottom: 20px;">
                        過去機車車載系統只能跑簡單的特徵對比運算，容易受到隧道、下雨、黑夜的影響。V.I.S.O.R. 選擇了 <strong>「純視覺 AI (Pure Vision AI)」</strong> 路線：
                    </p>""": """                    <p style="font-size: 14.5px; line-height: 1.7; margin-bottom: 20px;">
                        Past onboard systems only ran simple feature matching, failing in tunnels, rain, or night. V.I.S.O.R. pursues a Pure Vision AI approach:
                    </p>""",
                    
        """                            <li style="margin-bottom: 12px; font-size: 14px;"><strong>全局視野 (Global Context)：</strong>
                            基於卷積/自注意力機制的深度學習，即使目標部分被前方車輛遮擋，AI 仍能精確推理出車輛與車道輪廓。</li>""": """                            <li style="margin-bottom: 12px; font-size: 14px;"><strong>Global Context Extraction:</strong>
                            CNN/Self-Attention architecture allows the AI to infer vehicle and lane contours even when partially occluded.</li>""",
                            
        """                            <li style="margin-bottom: 12px; font-size: 14px;"><strong>擺脫了傳統邊緣偵測（如 Canny、Sobel）</strong>
                            需要工程師在不同天候反覆手動調整門檻值的致命缺陷。</li>""": """                            <li style="margin-bottom: 12px; font-size: 14px;"><strong>Eliminating Manual Thresholds:</strong>
                            Discards classical filters (e.g. Canny, Sobel) requiring engineers to manually recalibrate variables under different weather.</li>""",
                            
        """                            <li style="margin-bottom: 12px; font-size: 14px;"><strong>強健的泛化能力：</strong>
                            經由大規模多元天候與夜間路況數據集訓練，實現跨場景的自適應。</li>""": """                            <li style="margin-bottom: 12px; font-size: 14px;"><strong>Robust Generalization:</strong>
                            Trained on diverse weather, lighting, and night datasets to achieve adaptive performance across scenarios.</li>""",

        # --- Slide 6 ---
        """                    <div style="font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">主運算大腦 (8GB)</div>""": """                    <div style="font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Central Compute Core (8GB)</div>""",
        
        """                    <div style="font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">HUD 驅動節點</div>""": """                    <div style="font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">HUD Display Driver Node</div>""",
        
        """                    <p style="font-size: 11px; color: var(--text-muted); margin-bottom: 5px;">資料接收與格式化</p>""": """                    <p style="font-size: 11px; color: var(--text-muted); margin-bottom: 5px;">Data Receiver & Formatter</p>""",
        
        """                    <h3>分散式處理架構：解耦「資源密集推理」與「毫秒即時顯示」</h3>""": """                    <h3>Distributed Architecture: Decoupling Compute-Intensive AI from Real-Time Display</h3>""",
        
        """                    <p style="font-size: 15px; font-weight: 600; color: var(--brand-teal); margin-bottom: 20px;">
                        為何採用分散式雙板方案？
                    </p>""": """                    <p style="font-size: 15px; font-weight: 600; color: var(--brand-teal); margin-bottom: 20px;">
                        Why Dual-Node Architecture?
                    </p>""",
                    
        """                    <p style="font-size: 14.5px; line-height: 1.7; margin-bottom: 20px;">
                        過去單板運算單元若同時承擔 <strong>AI 影像推理、多執行緒影像擷取、快取控制與 HMI 渲染</strong>，極易因資源競爭造成顯示延遲、卡頓。
                    </p>""": """                    <p style="font-size: 14.5px; line-height: 1.7; margin-bottom: 20px;">
                        Running AI inference, frame acquisition, and display rendering on a single SBC often leads to latency and stuttering due to resource contention.
                    </p>""",
                    
        """                            <li style="margin-bottom: 15px; font-size: 14px;"><strong>Raspberry Pi 5 (運算核心)：</strong>
                            專職處理 320px 全流影像輸入、深度推理與目標追蹤.</li>""": """                            <li style="margin-bottom: 15px; font-size: 14px;"><strong>Raspberry Pi 5 (Core Engine):</strong>
                            Dedicated to 320px video stream acquisition, deep learning inference, and object tracking.</li>""",
                            
        """                            <li style="margin-bottom: 0; font-size: 14px;"><strong>Raspberry Pi Zero 2W (顯示驅動)：</strong>
                            體積小、功耗極低，放置於安全帽或儀表板端，接收輕量化的座標與警報資料，專職快速驅動 OLED 顯示。</li>""": """                            <li style="margin-bottom: 0; font-size: 14px;"><strong>Raspberry Pi Zero 2W (HUD Node):</strong>
                            Small form factor, ultra-low power. Installed in the helmet/dashboard, it receives lightweight telemetry and drives the OLED screen.</li>""",

        # --- Slide 8 ---
        """                        <p>
                            拖動下方滑桿模擬機車過彎時的<strong>滾轉角 ($\theta$)</strong> 變化，觀察系統如何透過卡爾曼濾波器動態旋轉校正 ROI：
                        </p>""": """                        <p>
                            Drag the slider below to simulate the motorcycle's roll angle during cornering. Observe how the system uses Kalman-filtered sensor data to rotate and correct the ROI in real-time:
                        </p>""",

        # --- Slide 9 ---
        """                        <p>
                            在無法搭載高成本光達的限制下，V.I.S.O.R. 實作了基於 <strong>相似三角形幾何投影</strong> 的測距演算法：
                        </p>""": """                        <p>
                            Without expensive LiDAR, V.I.S.O.R. implements a geometric distance estimation algorithm based on similar triangle projection:
                        </p>""",
                        
        """                        <p style="font-size: 14px;">
                            其中，先驗寬度以 COCO 類別統計平均值為基準（例如：標準轎車 $Known\\_Width \\approx 1.8\\text{m}$），並在相機校正階段算出特定焦距 ($Focal\\_Length$)。此方法在 15 米內近場預警中極具成本效益。
                        </p>""": """                        <p style="font-size: 14px;">
                            Where Known_Width is based on class statistics (e.g. standard car &approx; 1.8m) and Focal_Length is calibrated beforehand. This method is highly cost-effective for close-range warnings (within 15m).
                        </p>""",
                        
        """                        <p>
                            為了解決兩側及後方高速接近車輛的碰撞威脅，系統實作了 <strong>影像擴張感知演算法</strong>：
                        </p>""": """                        <p>
                            To handle vehicles approaching rapidly from the sides or rear, the system implements an image expansion rate algorithm:
                        </p>""",
                        
        """                            <li style="margin-bottom: 10px; font-size: 14px;">
                                監控特定目標（ID）的面積變化率 $Area\\_Ratio > 1.25$ 且其質心位移向下偏時，即判定該車急速逼近並發出警報。
                            </li>""": """                            <li style="margin-bottom: 10px; font-size: 14px;">
                                Monitors track ID area change rate $Area\\_Ratio > 1.25$ and its centroid shifts downward, triggering a looming alarm.
                            </li>""",

        # --- Slide 10 ---
        """                        <p style="font-size: 14px; margin-bottom: 12px;">
                            為了防止 AI 由於光影震動造成偵測包圍盒跳動（Flickering），造成警報系統頻繁閃爍，我們採用了 <strong>CentroidTracker</strong> 技術：
                        </p>""": """                        <p style="font-size: 14px; margin-bottom: 12px;">
                            To prevent flickering bounding boxes caused by vibrations or lighting changes, we implement a <strong>CentroidTracker</strong> with:
                        </p>""",
                        
        """                            <li style="margin-bottom: 8px; font-size: 13.5px;"><strong>歐幾里得距離關聯：</strong>
                                基於連續影格間目標質心 (Centroid) 的最小化二次歐氏距離，鎖定目標 ID。</li>""": """                            <li style="margin-bottom: 8px; font-size: 13.5px;"><strong>Euclidean Distance Association:</strong>
                                Minimizes quadratic Euclidean distance of centroids across frames to maintain unique IDs.</li>""",
                                
        """                            <li style="margin-bottom: 8px; font-size: 13.5px;"><strong>快取機制 (Max Disappeared)：</strong>
                                若該 AI 物體出現短暫遮擋，系統仍保留 5 影格快取。</li>""": """                            <li style="margin-bottom: 8px; font-size: 13.5px;"><strong>Cache Window (Max Disappeared):</strong>
                                Retains object tracks for up to 5 consecutive frames if occluded or missed by the detector.</li>""",
                                
        """                            <li style="margin-bottom: 0; font-size: 13.5px;"><strong>一階卡爾曼濾波：</strong>
                                對偵測包圍盒的座標進行時序平滑化。</li>""": """                            <li style="margin-bottom: 0; font-size: 13.5px;"><strong>Kalman Filter Integration:</strong>
                                Smooths out bounding box coordinates over time to reduce jitter.</li>""",
                                
        """                        <p>
                            在市區擁擠路段行車，停放在路側的兩排車輛會對視覺系統造成嚴重的 <strong>無效警報 (False Positives)</strong>。
                        </p>""": """                        <p>
                            In dense urban streets, parked vehicles along curbs often cause severe <strong>false alarms (False Positives)</strong>.
                        </p>""",
                        
        """                            <li style="margin-bottom: 10px; font-size: 13.5px;"><strong>動態虛擬車道：</strong>
                                僅鎖定 X 軸比例為 $0.25$ 至 $0.75$ 的主車道。</li>""": """                            <li style="margin-bottom: 10px; font-size: 13.5px;"><strong>Dynamic Virtual Lane:</strong>
                                Filters out distractions by locking onto the active lane region (X-axis ratio 0.25 to 0.75).</li>""",
                                
        """                            <li style="margin-bottom: 0; font-size: 13.5px;"><strong>威脅分級評估：</strong>
                                只有預測軌跡與虛擬主車道產生交集時，才會啟動高級碰撞預警評估。</li>""": """                            <li style="margin-bottom: 0; font-size: 13.5px;"><strong>Threat Escalation:</strong>
                                Collision risk is evaluated only when the predicted trajectory of a tracked vehicle intersects the virtual lane.</li>""",

        # --- Slide 11 ---
        """                    <p>
                        過去多數行車記錄器以手機直連 Wi-Fi 來傳輸數據。然而，這會導致智慧型手機作業系統判定該 AP 無法上網，從而<strong>鎖死或中斷手機行動網路 (4G/5G)</strong>，造成手機端 Google Maps 導航與音樂完全停擺。
                    </p>""": """                    <p>
                        Conventional dashcams require phone-to-camera Wi-Fi. However, smartphones detect the AP lacks internet and block cellular data (4G/5G), disabling navigation and streaming.
                    </p>""",
                    
        """                        <li style="margin-bottom: 12px; font-size: 14.5px;"><strong>App ↔ Pi 5 (藍牙 BLE GATT)：</strong>
                            兩端以輕量級藍牙 BLE 進行參數同步與控制，不佔用手機 Wi-Fi，保持 5G 行動網路正常運作。</li>""": """                        <li style="margin-bottom: 12px; font-size: 14.5px;"><strong>App &harr; Pi 5 (BLE GATT):</strong>
                            Uses lightweight Bluetooth for controls and updates, leaving cellular 5G active for navigation.</li>""",
                            
        """                        <li style="margin-bottom: 0; font-size: 14.5px;"><strong>Pi 5 ↔ Pi Zero HUD (UDP 2.4GHz AP)：</strong>
                            雙板之間使用專屬 UDP 廣播，繞過連線交握延遲，實現低於 15 毫秒的超低延遲渲染。</li>""": """                        <li style="margin-bottom: 0; font-size: 14.5px;"><strong>Pi 5 &harr; HUD (UDP 2.4GHz AP):</strong>
                            Uses direct UDP broadcasts, bypassing handshake latency to deliver telemetries in under 15ms.</li>""",

        # --- Slide 12 ---
        """                    <h3>數據分析與模型對比</h3>""": """                    <h3>Data Analysis & Model Comparison</h3>""",
        
        """                    <p>
                        點擊左側選項對比不同模型的辨識精度。結果表明，<strong>針對台灣道路二次訓練的 V.I.S.O.R. 專有數據集</strong> 相比原生 YOLOv8n 在夜間與大雨環境中表現更為突出：
                    </p>""": """                    <p>
                        Click tab buttons below to contrast model precisions. Fine-tuning on localized Taiwan traffic datasets yields superior precision over generic models in dark/rainy conditions:
                    </p>""",
                    
        """                        <li style="margin-bottom: 15px; font-size: 14px;"><strong>高頻震動抗性：</strong>
                            動態模糊噪聲注入技術，使震動下精準度提高 <strong>+10.4%</strong>。</li>""": """                        <li style="margin-bottom: 15px; font-size: 14px;"><strong>Vibration Robustness:</strong>
                            Motion blur noise injection increases accuracy under high vibrations by <strong>+10.4%</strong>.</li>""",
                            
        """                        <li style="margin-bottom: 0; font-size: 14px;"><strong>惡劣天候泛化：</strong>
                            雨霧生成對抗技術，夜雨偵測提升 <strong>+12.1%</strong>。</li>""": """                        <li style="margin-bottom: 0; font-size: 14px;"><strong>Extreme Weather Adaptation:</strong>
                            Adversarial fog/rain simulation improves night-rain precision by <strong>+12.1%</strong>.</li>""",

        # --- Slide 13 ---
        """                        <li style="margin-bottom: 12px; font-size: 14px;"><strong>影像縮放至 320 像素：</strong>
                            成功減少了 75% 的運算像素矩陣。</li>""": """                        <li style="margin-bottom: 12px; font-size: 14px;"><strong>320px Resolution Downscaling:</strong>
                            Reduces compute matrix by 75%.</li>""",
                            
        """                        <li style="margin-bottom: 12px; font-size: 14px;"><strong>跳影格處理技術 (Frame Skipping)：</strong>
                            在維持運動軌跡穩定前提下，跳過非關鍵幀，大幅釋放 CPU。</li>""": """                        <li style="margin-bottom: 12px; font-size: 14px;"><strong>Adaptive Frame Skipping:</strong>
                            Skips redundant background/lane updates to free CPU while keeping tracking smooth.</li>""",
                            
        """                        <li style="margin-bottom: 0; font-size: 14px;"><strong>結果：</strong>
                            推理幀率提升至 <strong>15 至 20 FPS</strong>，達到了即時行車預警系統的實用安全標準。</li>""": """                        <li style="margin-bottom: 0; font-size: 14px;"><strong>Result:</strong>
                            Inference speed surges to <strong>15-20 FPS</strong>, satisfying real-time safety system requirements.</li>""",
    }

    # Perform exact blocks replacements
    for target, replacement in blocks.items():
        if target in content:
            content = content.replace(target, replacement)
            print(f"[SUCCESS] Replaced slide HTML block: {repr(target[:30])}...")
        else:
            # Let's try spacing normalization
            norm_target = " ".join(target.split())
            # Find in normalized content
            print(f"[WARNING] Block not found exactly: {repr(target[:30])}...")
            # We will use simple replace with normalization if needed, but let's try direct matches first.
            
    # Save back
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("[INFO] Exact block translations finished.")

if __name__ == "__main__":
    translate_exact_html()
