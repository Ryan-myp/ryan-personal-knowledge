package bidding

import (
	"context"
	"fmt"
	"math/rand"
	"sync"
	"time"
)

// BidRequest 竞价请求
type BidRequest struct {
	UserID    string    `json:"user_id"`
	AdSlotID  string    `json:"ad_slot_id"`
	Timestamp time.Time `json:"timestamp"`
	Device    string    `json:"device"`
	Location  string    `json:"location"`
}

// BidResponse 竞价响应
type BidResponse struct {
	AdID      string  `json:"ad_id"`
	BidPrice  float64 `json:"bid_price"`
	CreativeID string `json:"creative_id"`
	TrackingURL string `json:"tracking_url"`
}

// BidEngine 竞价引擎
type BidEngine struct {
	ctrModel    *CTRModel
	cvrModel    *CVRModel
	targetCPA   float64
	targetROAS  float64
	bidHistory  map[string][]float64
	mu          sync.RWMutex
}

func NewBidEngine(targetCPA, targetROAS float64) *BidEngine {
	return &BidEngine{
		ctrModel:   NewCTRModel(),
		cvrModel:   NewCVRModel(),
		targetCPA:  targetCPA,
		targetROAS: targetROAS,
		bidHistory: make(map[string][]float64),
	}
}

// CalculateBid 计算出价
func (e *BidEngine) CalculateBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
	// 1. 预测 CTR
	ctr := e.ctrModel.Predict(req)
	
	// 2. 预测 CVR
	cvr := e.cvrModel.Predict(req)
	
	// 3. 计算 eCPM = CTR × CVR × 平均订单价值
	avgOrderValue := 100.0 // 假设平均订单价值 $100
	ecpm := ctr * cvr * avgOrderValue
	
	// 4. 根据出价策略计算最终出价
	bidPrice := e.calculateBidPrice(ecpm, ctr, cvr)
	
	// 5. 记录竞价历史
	e.recordBidHistory(req.AdSlotID, bidPrice)
	
	return &BidResponse{
		AdID:        fmt.Sprintf("ad_%s", req.AdSlotID),
		BidPrice:    bidPrice,
		CreativeID:  fmt.Sprintf("creative_%s", req.AdSlotID),
		TrackingURL: fmt.Sprintf("https://track.example.com/%s", req.AdSlotID),
	}, nil
}

func (e *BidEngine) calculateBidPrice(ecpm, ctr, cvr float64) float64 {
	// Target CPA 策略
	if e.targetCPA > 0 {
		baseBid := e.targetCPA * cvr
		// 加入质量评分因子
		qualityScore := e.getQualityScore(ctr)
		return baseBid * qualityScore
	}
	
	// Target ROAS 策略
	if e.targetROAS > 0 {
		return ecpm / e.targetROAS
	}
	
	// Lowest Cost 策略
	return ecpm * 0.8
}

func (e *BidEngine) getQualityScore(ctr float64) float64 {
	if ctr > 0.05 {
		return 1.2
	} else if ctr > 0.02 {
		return 1.0
	}
	return 0.8
}

func (e *BidEngine) recordBidHistory(adSlotID string, bidPrice float64) {
	e.mu.Lock()
	defer e.mu.Unlock()
	
	history := e.bidHistory[adSlotID]
	history = append(history, bidPrice)
	if len(history) > 100 {
		history = history[len(history)-100:]
	}
	e.bidHistory[adSlotID] = history
}

// CTRModel CTR 预测模型
type CTRModel struct {
	weights map[string]float64
}

func NewCTRModel() *CTRModel {
	return &CTRModel{
		weights: map[string]float64{
			"user_history": 0.4,
			"ad_relevance": 0.3,
			"position":     0.2,
			"device":       0.1,
		},
	}
}

func (m *CTRModel) Predict(req *BidRequest) float64 {
	// 简化的 CTR 预测
	baseCTR := 0.02 // 2% 基础 CTR
	
	// 基于用户历史调整
	if req.UserID == "user_123" {
		baseCTR *= 1.5
	}
	
	// 基于设备调整
	if req.Device == "mobile" {
		baseCTR *= 0.8
	}
	
	// 添加随机噪声
	baseCTR += rand.Float64()*0.01 - 0.005
	
	return baseCTR
}

// CVRModel CVR 预测模型
type CVRModel struct {
	weights map[string]float64
}

func NewCVRModel() *CVRModel {
	return &CVRModel{
		weights: map[string]float64{
			"user_intent": 0.5,
			"ad_quality":  0.3,
			"price":       0.2,
		},
	}
}

func (m *CVRModel) Predict(req *BidRequest) float64 {
	baseCVR := 0.05 // 5% 基础 CVR
	
	if req.UserID == "user_123" {
		baseCVR *= 1.3
	}
	
	baseCVR += rand.Float64()*0.01 - 0.005
	
	return baseCVR
}
