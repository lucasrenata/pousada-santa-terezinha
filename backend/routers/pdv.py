from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import models, schemas
from database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/pdv", tags=["PDV"])

# --- CAIXA ---

@router.get("/caixa/status", response_model=Optional[schemas.CaixaSessionResponse])
def get_caixa_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Busca a sessão de caixa aberta do usuário atual"""
    return db.query(models.CaixaSession).filter(
        models.CaixaSession.user_id == current_user.id,
        models.CaixaSession.status == models.CaixaStatus.ABERTO
    ).first()

@router.post("/caixa/abrir", response_model=schemas.CaixaSessionResponse)
def abrir_caixa(
    request: schemas.CaixaSessionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Abre um novo turno de caixa"""
    aberto = db.query(models.CaixaSession).filter(
        models.CaixaSession.user_id == current_user.id,
        models.CaixaSession.status == models.CaixaStatus.ABERTO
    ).first()
    
    if aberto:
        raise HTTPException(status_code=400, detail="Você já possui um caixa aberto.")
    
    nova_sessao = models.CaixaSession(
        user_id=current_user.id,
        opening_balance=request.opening_balance,
        status=models.CaixaStatus.ABERTO,
        tenant_id=current_user.tenant_id
    )
    db.add(nova_sessao)
    db.commit()
    db.refresh(nova_sessao)
    return nova_sessao

@router.post("/caixa/fechar", response_model=schemas.CaixaSessionResponse)
def fechar_caixa(
    closing_balance: float,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Fecha o caixa atual"""
    sessao = db.query(models.CaixaSession).filter(
        models.CaixaSession.user_id == current_user.id,
        models.CaixaSession.status == models.CaixaStatus.ABERTO
    ).first()
    
    if not sessao:
        raise HTTPException(status_code=404, detail="Nenhuma sessão de caixa aberta encontrada.")
    
    # Gerar Resumo antes de fechar
    movements = db.query(models.CaixaMovement).filter(models.CaixaMovement.session_id == sessao.id).all()
    
    summary = {
        "user_name": current_user.full_name or current_user.username,
        "opening_balance": sessao.opening_balance,
        "vendas_dinheiro": sum(m.amount for m in movements if m.type == models.CaixaMovementType.VENDA and m.payment_method == models.PaymentMethod.DINHEIRO),
        "vendas_pix": sum(m.amount for m in movements if m.type == models.CaixaMovementType.VENDA and m.payment_method == models.PaymentMethod.PIX),
        "vendas_debito": sum(m.amount for m in movements if m.type == models.CaixaMovementType.VENDA and m.payment_method == models.PaymentMethod.DEBITO),
        "vendas_credito": sum(m.amount for m in movements if m.type == models.CaixaMovementType.VENDA and m.payment_method == models.PaymentMethod.CREDITO),
        "entradas_total": sum(m.amount for m in movements if m.type == models.CaixaMovementType.SUPRIMENTO),
        "retiradas_total": sum(m.amount for m in movements if m.type in [models.CaixaMovementType.SANGRIA, models.CaixaMovementType.RETIRADA]),
        "comandas_processadas": len([m for m in movements if m.type == models.CaixaMovementType.VENDA]),
    }
    
    # Saldo Dinheiro = Abertura + Vendas Dinheiro + Suprimentos - (Sangrias + Retiradas)
    summary["saldo_dinheiro"] = summary["opening_balance"] + summary["vendas_dinheiro"] + summary["entradas_total"] - summary["retiradas_total"]
    # Saldo Geral = Saldo Dinheiro + Vendas Outros Métodos
    summary["saldo_geral"] = summary["saldo_dinheiro"] + summary["vendas_pix"] + summary["vendas_debito"] + summary["vendas_credito"]
    
    sessao.status = models.CaixaStatus.FECHADO
    sessao.closing_balance = closing_balance
    sessao.closed_at = datetime.now()
    sessao.summary_json = summary # PERSISTÊNCIA DO RESUMO
    
    db.commit()
    db.refresh(sessao)
    return sessao

@router.post("/caixa/movimentar", response_model=schemas.CaixaMovementResponse)
def movimentar_caixa(
    request: schemas.CaixaMovementCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Registra sangria ou suprimento no caixa"""
    sessao = db.query(models.CaixaSession).filter(
        models.CaixaSession.user_id == current_user.id,
        models.CaixaSession.status == models.CaixaStatus.ABERTO
    ).first()
    
    if not sessao:
        raise HTTPException(status_code=400, detail="Caixa fechado. Abra o caixa primeiro.")
    
    movimento = models.CaixaMovement(
        session_id=sessao.id,
        type=request.type,
        amount=request.amount,
        description=request.description,
        tenant_id=current_user.tenant_id
    )
    db.add(movimento)
    db.commit()
    db.refresh(movimento)
    return movimento

@router.get("/caixa/summary", response_model=schemas.CaixaSummaryResponse)
def get_caixa_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Busca o resumo financeiro detalhado da sessão ativa"""
    sessao = db.query(models.CaixaSession).filter(
        models.CaixaSession.user_id == current_user.id,
        models.CaixaSession.status == models.CaixaStatus.ABERTO
    ).first()
    
    if not sessao:
        raise HTTPException(status_code=404, detail="Nenhum caixa aberto.")
    
    movements = db.query(models.CaixaMovement).filter(models.CaixaMovement.session_id == sessao.id).all()
    
    res = {
        "opening_balance": sessao.opening_balance,
        "vendas_dinheiro": sum(m.amount for m in movements if m.type == models.CaixaMovementType.VENDA and m.payment_method == models.PaymentMethod.DINHEIRO),
        "vendas_pix": sum(m.amount for m in movements if m.type == models.CaixaMovementType.VENDA and m.payment_method == models.PaymentMethod.PIX),
        "vendas_debito": sum(m.amount for m in movements if m.type == models.CaixaMovementType.VENDA and m.payment_method == models.PaymentMethod.DEBITO),
        "vendas_credito": sum(m.amount for m in movements if m.type == models.CaixaMovementType.VENDA and m.payment_method == models.PaymentMethod.CREDITO),
        "entradas_total": sum(m.amount for m in movements if m.type == models.CaixaMovementType.SUPRIMENTO),
        "retiradas_total": sum(m.amount for m in movements if m.type in [models.CaixaMovementType.SANGRIA, models.CaixaMovementType.RETIRADA]),
        "comandas_processadas": len([m for m in movements if m.type == models.CaixaMovementType.VENDA]),
        "movements": movements
    }
    
    # Saldo Dinheiro = Abertura + Vendas Dinheiro + Suprimentos - (Sangrias + Retiradas)
    res["saldo_dinheiro"] = res["opening_balance"] + res["vendas_dinheiro"] + res["entradas_total"] - res["retiradas_total"]
    
    # Saldo Geral = Saldo Dinheiro + Vendas Outros Métodos
    res["saldo_geral"] = res["saldo_dinheiro"] + res["vendas_pix"] + res["vendas_debito"] + res["vendas_credito"]
    
    return res

# --- COMANDAS ---

@router.post("/comandas/", response_model=schemas.ComandaResponse)
def criar_comanda(
    request: schemas.ComandaCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Cria uma nova comanda ou retorna uma existente se já estiver ABERTA"""
    # 1. Verifica se já existe uma comanda ABERTA para este identificador neste tenant
    comanda_existente = db.query(models.Comanda).filter(
        models.Comanda.identificador == request.identificador,
        models.Comanda.status == models.ComandaStatus.ABERTA,
        models.Comanda.tenant_id == current_user.tenant_id
    ).first()

    if comanda_existente:
        return comanda_existente

    # 2. Caso contrário, cria uma nova branquinha
    sessao = db.query(models.CaixaSession).filter(
        models.CaixaSession.user_id == current_user.id,
        models.CaixaSession.status == models.CaixaStatus.ABERTO
    ).first()
    
    nova_comanda = models.Comanda(
        identificador=request.identificador,
        booking_id=request.booking_id,
        session_id=sessao.id if sessao else None,
        status=models.ComandaStatus.ABERTA,
        tenant_id=current_user.tenant_id
    )
    db.add(nova_comanda)
    db.commit()
    db.refresh(nova_comanda)
    return nova_comanda

@router.get("/comandas/", response_model=List[schemas.ComandaResponse])
def listar_comandas_abertas(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Lista todas as comandas abertas do tenant"""
    return db.query(models.Comanda).filter(
        models.Comanda.status == models.ComandaStatus.ABERTA
    ).all()

@router.post("/comandas/{comanda_id}/itens/", response_model=schemas.ComandaItemResponse)
def adicionar_item_comanda(
    comanda_id: int,
    request: schemas.ComandaItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Adiciona um item à comanda"""
    comanda = db.query(models.Comanda).filter(models.Comanda.id == comanda_id).first()
    if not comanda or comanda.status != models.ComandaStatus.ABERTA:
        raise HTTPException(status_code=400, detail="Comanda não encontrada ou já finalizada.")
    
    novo_item = models.ComandaItem(
        comanda_id=comanda_id,
        product_id=request.product_id,
        quantity=request.quantity,
        unit_price=request.unit_price,
        description=request.description,
        type=request.type,
        tenant_id=current_user.tenant_id
    )
    db.add(novo_item)
    
    # Atualiza total da comanda
    item_total = request.unit_price * request.quantity
    comanda.total = (comanda.total or 0.0) + item_total
    
    db.commit()
    db.refresh(novo_item)
    return novo_item

@router.delete("/comandas/itens/{item_id}")
def remover_item_comanda(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Remove um item da comanda e subtrai do total"""
    item = db.query(models.ComandaItem).filter(models.ComandaItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    
    comanda = item.comanda
    if comanda.status != models.ComandaStatus.ABERTA:
        raise HTTPException(status_code=400, detail="Não é possível alterar uma comanda finalizada.")
    
    comanda.total -= (item.unit_price * item.quantity)
    db.delete(item)
    db.commit()
    return {"message": "Item removido"}

@router.patch("/comandas/itens/{item_id}", response_model=schemas.ComandaItemResponse)
def atualizar_item_comanda(
    item_id: int,
    request: schemas.ComandaItemUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Atualiza a quantidade de um item e ajusta o total da comanda"""
    item = db.query(models.ComandaItem).filter(models.ComandaItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    
    comanda = item.comanda
    if comanda.status != models.ComandaStatus.ABERTA:
        raise HTTPException(status_code=400, detail="Não é possível alterar uma comanda finalizada.")

    # Diferença no total
    old_item_total = item.unit_price * item.quantity
    new_item_total = item.unit_price * request.quantity
    
    # Atualiza item e comanda
    item.quantity = request.quantity
    comanda.total = (comanda.total - old_item_total) + new_item_total
    
    db.commit()
    db.refresh(item)
    return item

def _process_comanda_finalization(comanda: models.Comanda, request: schemas.CloseComandaRequest, db: Session, current_user: models.User):
    # 1. Vínculo Antecipado com Quarto/Reserva
    if request.lancada_no_quarto:
        if request.booking_id:
            comanda.booking_id = request.booking_id
        
        if not comanda.booking_id:
            raise HTTPException(status_code=400, detail=f"Comanda #{comanda.identificador} não está vinculada a nenhuma reserva (Quarto). Escolha o hóspede primeiro.")

    # 2. Processamento de Itens
    for item in comanda.items:
        # Baixa de Estoque (Apenas para Venda Direta)
        if not request.lancada_no_quarto:
            if item.product_id:
                produto = db.query(models.Product).filter(models.Product.id == item.product_id).first()
                if produto:
                    produto.stock_quantity -= int(item.quantity)
        
        # Lançamento de Consumo na Reserva (Apenas para Lançar no Quarto)
        if request.lancada_no_quarto:
            consumo = models.Consumption(
                booking_id=comanda.booking_id,
                product_id=item.product_id,
                quantity=int(item.quantity),
                unit_price=item.unit_price,
                tenant_id=current_user.tenant_id
            )
            db.add(consumo)
    
    # 3. Criar Registro Histórico (Snapshot) da Venda
    final_amount = max(0.0, comanda.total - getattr(request, 'discount', 0.0))
    
    registro_venda = models.PDVSale(
        comanda_identificador=comanda.identificador,
        total_amount=final_amount,
        discount=getattr(request, 'discount', 0.0),
        payment_method=request.payment_method, # Pode ser None se for lançamento no quarto
        user_id=current_user.id,
        session_id=comanda.session_id,
        tenant_id=current_user.tenant_id
    )
    db.add(registro_venda)
    db.flush() # Para gerar o ID da venda antes de criar os itens

    for item in comanda.items:
        snapshot_item = models.PDVSaleItem(
            sale_id=registro_venda.id,
            product_name=item.product.name if item.product else item.description or "Produto Manual",
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_item=item.unit_price * item.quantity,
            tenant_id=current_user.tenant_id
        )
        db.add(snapshot_item)

    # 4. Finalização de Status e Registros Financeiros (Venda Direta)
    if request.lancada_no_quarto:
        comanda.status = models.ComandaStatus.LANCADA_NO_QUARTO
    else:
        receita = models.Revenue(
            description=f"PDV: Comanda #{comanda.identificador}",
            amount=final_amount,
            category=models.RevenueCategory.CONSUMO,
            payment_method=request.payment_method,
            booking_id=comanda.booking_id,
            created_by_user=current_user.username,
            tenant_id=current_user.tenant_id
        )
        db.add(receita)
        
        if comanda.session_id:
            mov = models.CaixaMovement(
                session_id=comanda.session_id,
                type=models.CaixaMovementType.VENDA,
                amount=final_amount,
                description=f"Venda Comanda #{comanda.identificador}",
                payment_method=request.payment_method,
                tenant_id=current_user.tenant_id
            )
            db.add(mov)

        comanda.status = models.ComandaStatus.PAGA
    return comanda

@router.post("/comandas/{comanda_id}/finalizar")
def finalizar_comanda(
    comanda_id: int,
    request: schemas.CloseComandaRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Finaliza a comanda: Lança no quarto ou registra pagamento direto"""
    comanda = db.query(models.Comanda).filter(models.Comanda.id == comanda_id).first()
    if not comanda or comanda.status != models.ComandaStatus.ABERTA:
        raise HTTPException(status_code=400, detail="Comanda inválida ou já finalizada.")
    
    _process_comanda_finalization(comanda, request, db, current_user)
    db.commit()
    return {"message": "Comanda finalizada com sucesso", "status": comanda.status}

@router.post("/comandas/batch-finalizar")
def batch_finalizar_comanda(
    request: schemas.BatchCloseComandaRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Finaliza múltiplas comandas de uma vez"""
    comandas = db.query(models.Comanda).filter(
        models.Comanda.id.in_(request.comanda_ids),
        models.Comanda.status == models.ComandaStatus.ABERTA
    ).all()
    
    if len(comandas) != len(request.comanda_ids):
        raise HTTPException(status_code=400, detail="Uma ou mais comandas são inválidas ou já foram finalizadas.")
    
    # No caso de batch, aplicamos o desconto total no processamento individual da última comanda 
    # ou distribuímos. Para simplificar e manter integridade, aplicamos o desconto na primeira.
    # OBS: O frontend enviará o desconto total do lote.
    for i, comanda in enumerate(comandas):
        comanda_discount = request.discount if i == 0 else 0.0
        single_req = schemas.CloseComandaRequest(
            payment_method=request.payment_method,
            lancada_no_quarto=request.lancada_no_quarto,
            discount=comanda_discount
        )
        _process_comanda_finalization(comanda, single_req, db, current_user)
    
    db.commit()
    return {"message": f"{len(comandas)} comandas finalizadas com sucesso"}
