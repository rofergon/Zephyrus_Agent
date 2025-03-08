const express = require('express');
const router = express.Router();
const contractInteractionService = require('../services/contractInteraction');

// Middleware para validar el cuerpo de la petición
const validateContractRequest = (req, res, next) => {
    const { contractAddress, abi, functionName } = req.body;
    
    if (!contractAddress || !abi || !functionName) {
        return res.status(400).json({
            success: false,
            error: 'Missing required fields: contractAddress, abi, and functionName are required'
        });
    }

    // Validar formato de dirección Ethereum
    if (!/^0x[a-fA-F0-9]{40}$/.test(contractAddress)) {
        return res.status(400).json({
            success: false,
            error: 'Invalid contract address format'
        });
    }

    next();
};

// Función para manejar la serialización de BigInt
const handleBigIntSerialization = (obj) => {
    if (typeof obj === 'bigint') {
        return obj.toString();
    } else if (Array.isArray(obj)) {
        return obj.map(handleBigIntSerialization);
    } else if (typeof obj === 'object' && obj !== null) {
        const result = {};
        for (const key in obj) {
            result[key] = handleBigIntSerialization(obj[key]);
        }
        return result;
    }
    return obj;
};

// Endpoint para leer datos del contrato (funciones view/pure)
router.post('/read', validateContractRequest, async (req, res) => {
    try {
        const { contractAddress, abi, functionName, inputs = [] } = req.body;
        const result = await contractInteractionService.readContract(
            contractAddress,
            abi,
            functionName,
            inputs
        );
        res.json(handleBigIntSerialization(result));
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// Endpoint para escribir datos en el contrato (funciones que modifican estado)
router.post('/write', validateContractRequest, async (req, res) => {
    try {
        const { contractAddress, abi, functionName, inputs = [] } = req.body;
        const result = await contractInteractionService.writeContract(
            contractAddress,
            abi,
            functionName,
            inputs
        );
        res.json(handleBigIntSerialization(result));
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// Endpoint para obtener eventos del contrato
router.post('/events', validateContractRequest, async (req, res) => {
    try {
        const { contractAddress, abi, eventName, filter = {} } = req.body;
        const result = await contractInteractionService.getEvents(
            contractAddress,
            abi,
            eventName,
            filter
        );
        res.json(handleBigIntSerialization(result));
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

module.exports = router; 